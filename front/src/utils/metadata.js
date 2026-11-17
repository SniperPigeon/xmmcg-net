// 上传前在浏览器内预读元数据，只用于预填表单，用户仍可修改；服务端仍要求填写。

// maidata.txt 每行形如 `&key=value`；可能带 BOM 或 CRLF。
const maidataField = (text, key) => {
  const match = text.match(new RegExp(`^\\s*&${key}=([^\\r\\n]*)`, 'm'))
  return match ? match[1].trim() : ''
}

export const parseMaidata = (text) => ({
  title: maidataField(text, 'title'),
  // 优先全局名义，其次 Master（5）和 Re:Master（6）的名义；均为空时留给用户填写。
  designer:
    maidataField(text, 'des') || maidataField(text, 'des_?5') || maidataField(text, 'des_?6'),
})

export const readMaidata = async (file) => parseMaidata(await file.text())

// 读取 ID3 / Vorbis / MP4 等标签中的标题；解析库较大，仅在选择音频时加载。
export const readAudioTitle = async (file) => {
  const { parseBlob } = await import('music-metadata')
  const metadata = await parseBlob(file, { skipCovers: true, duration: false })
  return metadata.common.title?.trim() || ''
}

// 只覆盖空白或上次自动填入的值，不覆盖用户手动输入的内容。
export const createPrefill = (target) => {
  const filled = {}
  return {
    apply(key, value) {
      const current = (target[key] || '').trim()
      if (current && current !== filled[key]) return false
      target[key] = value
      filled[key] = value
      return true
    },
    reset() {
      for (const key of Object.keys(filled)) delete filled[key]
    },
  }
}
