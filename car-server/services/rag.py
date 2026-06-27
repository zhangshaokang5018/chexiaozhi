# services/rag.py —— 【B 角色】本地 RAG 检索（sentence-transformers + 本地 Chroma）
#
# 完全本地、离线运行，不需要任何 API Key：
#   - Embedding：本地模型 BAAI/bge-small-zh-v1.5（中文检索）
#   - 向量库：本地 Chroma（car-server/.chroma）
#
# 适用知识库：症状(symptom)、成本(cost)、故障码(dtc)。
#
# 能力：
#   is_available()               本地模型是否可用（已安装且能加载）
#   build_index()                读取知识库 → 本地向量化 → 写入本地 Chroma
#   search(kind, query, top_k)   语义检索，返回 [{item, distance}]；不可用时返回 None（调用方退回关键词）
#
# 命令行：在 car-server 目录执行  python -m services.rag build   构建/重建索引
#   注意：首次运行会从 HuggingFace 下载模型（约 100MB，仅此一次需联网），之后完全离线。
#
# 设计原则：任何一步失败（模型缺失 / 下载失败 / 索引缺失）都返回 None，让调用方平滑退回
# 关键词匹配，保证服务永远能跑。

import json
import os
import sys
from typing import TypedDict

from routes.kb import load_kb

# 本地中文检索模型；可用环境变量 EMBEDDING_MODEL_LOCAL 覆盖
MODEL_NAME = os.environ.get("EMBEDDING_MODEL_LOCAL", "BAAI/bge-small-zh-v1.5")
# bge 中文模型建议给“查询”加指令前缀以提升检索效果（文档侧不加）
_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

_CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".chroma")
_RAG_KINDS = ("symptom", "cost", "dtc")

_model = None
_client = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def is_available() -> bool:
    try:
        _get_model()
        return True
    except Exception as e:
        print(f"[rag] 本地模型不可用，将退回关键词匹配，原因: {e}")
        return False


def _get_client():
    global _client
    if _client is None:
        import chromadb
        from chromadb.config import Settings

        _client = chromadb.PersistentClient(
            path=_CHROMA_DIR, settings=Settings(anonymized_telemetry=False)
        )
    return _client


def _coll_name(kind: str) -> str:
    return f"kb_{kind}"


def _doc_text(kind: str, item: dict) -> str:
    """把一条知识拼成用于向量化的文本。"""
    if kind == "symptom":
        return " ".join(item.get("keywords", [])) + " " + item.get("fault", "") + " " + item.get("tip", "")
    if kind == "cost":
        return f'{item.get("item", "")} {item.get("cat", "")} {item.get("tip", "")}'
    if kind == "dtc":
        # 绑定三字段：故障码 + 对应故障 + 小白解释（再加可能原因），
        # 使得用户用代码、专业描述或大白话任意一种都能检索到整条
        return (
            f'{item.get("code", "")} {item.get("desc", "")} '
            f'{item.get("plain", "")} {item.get("cause", "")}'
        )
    return json.dumps(item, ensure_ascii=False)


def _embed(texts: list, is_query: bool = False) -> list:
    """本地向量化；返回归一化后的向量列表。"""
    model = _get_model()
    inputs = [_QUERY_INSTRUCTION + t for t in texts] if is_query else list(texts)
    vecs = model.encode(inputs, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def build_index() -> bool:
    """构建/重建症状库、成本库、故障码库的本地向量索引。"""
    client = _get_client()
    for kind in _RAG_KINDS:
        items = load_kb(kind) or []
        if not items:
            continue
        docs = [_doc_text(kind, it) for it in items]
        embs = _embed(docs, is_query=False)
        try:
            client.delete_collection(_coll_name(kind))
        except Exception:
            pass
        coll = client.create_collection(_coll_name(kind), metadata={"hnsw:space": "cosine"})
        coll.add(
            ids=[f"{kind}-{i}" for i in range(len(items))],
            embeddings=embs,
            documents=docs,
            metadatas=[{"raw": json.dumps(it, ensure_ascii=False)} for it in items],
        )
        print(f"[rag] {kind}: 已索引 {len(items)} 条")
    return True


def search(kind: str, query: str, top_k: int = 3, max_distance: float = None):
    """语义检索。返回 [{item, distance}]（distance 越小越相关）；不可用时返回 None。"""
    if kind not in _RAG_KINDS:
        return None
    try:
        coll = _get_client().get_collection(_coll_name(kind))
        if coll.count() == 0:
            return None
        qemb = _embed([query], is_query=True)[0]
        res = coll.query(query_embeddings=[qemb], n_results=top_k)
        out = []
        for meta, dist in zip(res["metadatas"][0], res["distances"][0]):
            if max_distance is not None and dist > max_distance:
                continue
            out.append({"item": json.loads(meta["raw"]), "distance": dist})
        return out
    except Exception as e:
        print(f"[rag] search 退回关键词匹配，原因: {e}")
        return None


# ===================== LangGraph 检索节点（让 RAG 也跑在图里，统一管理） =====================
#
# 设计：把 search() 包装成一个可复用的 LangGraph 节点工厂。任何智能体（maintain 等）
# 都能把检索作为图里的一个“显式节点”插入，而不是埋在某个函数内部，方便观测/复用/编排。
#
# 约定：节点从 state[query_key] 取查询文本，把命中结果写入 state[out_key]
#       （格式同 search()：[{item, distance}]；不可用/未命中写入 []）。

# 检索状态：单独跑 RAG 子图时使用；嵌入其他图时按 TypedDict total=False 兼容
class RetrievalState(TypedDict, total=False):
    text: str          # 输入：查询文本
    rag_hits: list     # 输出：命中列表 [{item, distance}]


def make_retrieve_node(
    kind: str,
    *,
    top_k: int = 5,
    max_distance: float = None,
    query_key: str = "text",
    out_key: str = "rag_hits",
):
    """生成一个 LangGraph 检索节点：读 state[query_key] → 写 state[out_key]=命中列表。

    用法（在某个智能体的图里）：
        g.add_node("retrieve", make_retrieve_node("cost", top_k=1, max_distance=0.55))
    """
    def _retrieve_node(state: dict) -> dict:
        query = state.get(query_key, "") or ""
        hits = search(kind, query, top_k=top_k, max_distance=max_distance) or []
        return {out_key: hits}

    return _retrieve_node


_retrieval_graphs = {}


def build_retrieval_graph(kind: str, *, top_k: int = 5, max_distance: float = None):
    """把单个知识库的检索编译成一张独立的 LangGraph 图（START→retrieve→END），按 kind 缓存。

    让 RAG 检索本身就是“一张图”，可单独 invoke，便于统一管理与调试：
        graph = build_retrieval_graph("cost", top_k=1, max_distance=0.55)
        hits = graph.invoke({"text": "换机油多少钱"})["rag_hits"]
    """
    cache_key = (kind, top_k, max_distance)
    if cache_key not in _retrieval_graphs:
        from langgraph.graph import StateGraph, START, END

        g = StateGraph(RetrievalState)
        g.add_node("retrieve", make_retrieve_node(
            kind, top_k=top_k, max_distance=max_distance))
        g.add_edge(START, "retrieve")
        g.add_edge("retrieve", END)
        _retrieval_graphs[cache_key] = g.compile()
    return _retrieval_graphs[cache_key]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        if not is_available():
            print("本地模型不可用，无法构建索引。请确认已 pip install sentence-transformers，且首次构建可联网下载模型。")
            sys.exit(1)
        build_index()
        print("[rag] 索引构建完成（本地模型，离线可用）")
    else:
        print(f"未知命令: {cmd}（可用: build）")
