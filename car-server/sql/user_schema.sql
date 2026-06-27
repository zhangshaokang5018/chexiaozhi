-- =============================================================
-- 车小智 · 用户体系数据库 schema（B 负责）
-- =============================================================
-- 用途：存放 B 用户体系（登录 / 资料 / 隐私 / 车辆 / 统计）的数据。
-- A 的主业务（chat / kb / context / receipt / agents / rag）不使用本库，
-- 也不依赖 MySQL；本库只服务 /api/user/*。
--
-- 初始化方式（任选其一，详见 car-server/README.md「用户体系数据库」一节）：
--   1) 命令行：  mysql -u root -p < sql/user_schema.sql
--   2) 脚本：    .venv\Scripts\python -m services.user_init   （由 B 实现，可选）
--
-- 字符集统一 utf8mb4，避免昵称/车型中的 emoji 与中文乱码。
-- =============================================================

CREATE DATABASE IF NOT EXISTS chexiaozhi_user
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE chexiaozhi_user;

-- -------------------------------------------------------------
-- 1. users —— 账号与基础资料
--    user_id 为对外稳定主键（契约里形如 user_10001 / guest_xxx），
--    由 B 在登录时生成；A 只消费这个 user_id。
--    phone 明文落库但对外只返回 phone_masked（见 03 §10.2/§10.4）。
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  user_id           VARCHAR(64)  NOT NULL COMMENT '对外稳定用户ID',
  login_type        VARCHAR(16)  NOT NULL DEFAULT 'guest' COMMENT 'wechat | guest',
  openid            VARCHAR(64)  NULL COMMENT '微信 openid，guest 为空',
  anonymous_id      VARCHAR(64)  NULL COMMENT '游客设备标识',
  session_token     VARCHAR(128) NULL COMMENT '登录态 token，仅登录响应返回一次',
  nickname          VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '昵称',
  avatar_url        VARCHAR(255) NOT NULL DEFAULT '' COMMENT '头像URL',
  phone             VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '手机号(敏感,仅脱敏返回)',
  profile_completed TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '资料是否完善',
  created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uk_openid (openid),
  KEY idx_anonymous (anonymous_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户账号与基础资料';

-- -------------------------------------------------------------
-- 2. user_privacy —— 隐私 / 私人信息设置（对应 GET/PATCH /api/user/privacy）
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_privacy (
  user_id                         VARCHAR(64) NOT NULL,
  phone_authorized                TINYINT(1)  NOT NULL DEFAULT 0 COMMENT '是否授权手机号',
  show_vin                        TINYINT(1)  NOT NULL DEFAULT 0 COMMENT '是否展示完整VIN(默认脱敏)',
  share_diagnosis_for_improvement TINYINT(1)  NOT NULL DEFAULT 0 COMMENT '是否允许诊断数据用于改进',
  data_retention_days             INT         NOT NULL DEFAULT 180 COMMENT '数据保留天数',
  updated_at                      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  CONSTRAINT fk_privacy_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户隐私设置';

-- -------------------------------------------------------------
-- 3. user_vehicle —— 用户车辆资料（对应 GET/PATCH /api/user/vehicle）
--    字段与 A 的 /api/context 对齐；MVP 阶段两套存储分离，集成时再决定是否合库。
--    vin 明文落库，对外是否展示遵守 user_privacy.show_vin，默认脱敏。
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_vehicle (
  user_id    VARCHAR(64)  NOT NULL,
  car_model  VARCHAR(128) NOT NULL DEFAULT '' COMMENT '车型',
  vin        VARCHAR(32)  NOT NULL DEFAULT '' COMMENT 'VIN(敏感,脱敏展示)',
  mileage    VARCHAR(32)  NOT NULL DEFAULT '' COMMENT '里程, 如 38,500 km',
  location   VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '城市',
  updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  CONSTRAINT fk_vehicle_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户车辆资料';

-- -------------------------------------------------------------
-- 4. user_stats —— 我的页统计（对应 GET /api/user/stats）
--    MVP 阶段由 B 维护/模拟；consult_count、receipt_count 等若要读 A 的真实数据，
--    先在 03 文档约定接口，再单独做集成，不直接改 A 的 services/context.py。
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_stats (
  user_id         VARCHAR(64) NOT NULL,
  consult_count   INT         NOT NULL DEFAULT 0 COMMENT '咨询次数',
  receipt_count   INT         NOT NULL DEFAULT 0 COMMENT '维修记录数',
  estimated_saved INT         NOT NULL DEFAULT 0 COMMENT '预估节省金额(元)',
  favorite_count  INT         NOT NULL DEFAULT 0 COMMENT '收藏数',
  updated_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  CONSTRAINT fk_stats_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户统计';

-- -------------------------------------------------------------
-- 可选：本地联调用的演示账号（与 03 契约示例一致）。
-- 正式环境请删除或改由登录流程创建。
-- -------------------------------------------------------------
INSERT INTO users (user_id, login_type, nickname, phone, profile_completed)
VALUES ('user_10001', 'wechat', '车小智用户', '13800008000', 1)
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

INSERT INTO user_privacy (user_id) VALUES ('user_10001')
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

INSERT INTO user_vehicle (user_id, car_model, vin, mileage, location)
VALUES ('user_10001', '2022款 丰田 卡罗拉 1.2T 豪华版', 'LFMAP22CXXX123456', '38,500 km', '北京')
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

INSERT INTO user_stats (user_id, consult_count, receipt_count, estimated_saved)
VALUES ('user_10001', 12, 3, 680)
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;
