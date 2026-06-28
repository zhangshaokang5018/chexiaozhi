export interface SelectedVehicleImage {
  tempFilePath: string
  size: number
  label: string
}

export function chooseVehicleImage(label: string): Promise<SelectedVehicleImage> {
  const imageLabel = (label || '报价单').trim()
  return new Promise((resolve, reject) => {
    const wxAny = wx as any
    if (typeof wxAny.chooseMedia === 'function') {
      wxAny.chooseMedia({
        count: 1,
        mediaType: ['image'],
        sourceType: ['camera', 'album'],
        success: (res: any) => {
          const file = Array.isArray(res.tempFiles) ? res.tempFiles[0] : null
          const tempFilePath = file && file.tempFilePath ? String(file.tempFilePath) : ''
          if (!tempFilePath) {
            reject(new Error('未选择图片'))
            return
          }
          resolve({
            tempFilePath,
            size: Number(file.size || 0),
            label: imageLabel,
          })
        },
        fail: reject,
      })
      return
    }

    wx.chooseImage({
      count: 1,
      sourceType: ['camera', 'album'],
      success: (res) => {
        const tempFilePath = res.tempFilePaths && res.tempFilePaths[0] ? res.tempFilePaths[0] : ''
        if (!tempFilePath) {
          reject(new Error('未选择图片'))
          return
        }
        const file = res.tempFiles && res.tempFiles[0]
        resolve({
          tempFilePath,
          size: file ? Number(file.size || 0) : 0,
          label: imageLabel,
        })
      },
      fail: reject,
    })
  })
}

export function isChooseMediaCancel(err: unknown): boolean {
  const message = String((err as { errMsg?: string } | undefined)?.errMsg || err || '')
  return message.toLowerCase().includes('cancel')
}
