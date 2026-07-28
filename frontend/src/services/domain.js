import api from './api'

export const authService = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
  register: (payload) => api.post('/auth/register', payload),
}

export const dashboardService = {
  get: () => api.get('/dashboard'),
}

export const proxyService = {
  list: (params) => api.get('/proxies', { params }),
  get: (id) => api.get(`/proxies/${id}`),
  create: (payload) => api.post('/proxies', payload),
  update: (id, payload) => api.patch(`/proxies/${id}`, payload),
  remove: (id) => api.delete(`/proxies/${id}`),
  test: (id) => api.post(`/proxies/${id}/test`),
  import: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/proxies/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const logService = {
  list: (params) => api.get('/logs', { params }),
}

export const gatewayService = {
  info: () => api.get('/gateway/info'),
}
