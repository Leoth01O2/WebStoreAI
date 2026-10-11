/**
 * Centralized API Client for StoreFlow AI
 * Directly connects to FastAPI Backend via /api/v1
 */

const API_BASE = '/api/v1';

export const getAuthToken = () => {
  return localStorage.getItem('storeflow_token');
};

export const setAuthToken = (token) => {
  if (token) {
    localStorage.setItem('storeflow_token', token);
  } else {
    localStorage.removeItem('storeflow_token');
  }
};

export const getUserData = () => {
  const data = localStorage.getItem('storeflow_user');
  return data ? JSON.parse(data) : null;
};

export const setUserData = (user) => {
  if (user) {
    localStorage.setItem('storeflow_user', JSON.stringify(user));
  } else {
    localStorage.removeItem('storeflow_user');
  }
};

async function request(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const config = {
    ...options,
    headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, config);

  // Handle Unauthorized automatically
  if (response.status === 401) {
    setAuthToken(null);
    setUserData(null);
    if (!window.location.pathname.includes('/login')) {
      window.location.reload();
    }
    throw new Error('Phiên đăng nhập đã hết hạn hoặc không hợp lệ.');
  }

  // File downloads / Blobs
  if (options.responseType === 'blob') {
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || 'Không thể tải tệp tin');
    }
    return await response.blob();
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    let errorMsg = 'Có lỗi xảy ra trong quá trình xử lý';
    if (data && data.detail) {
      if (typeof data.detail === 'string') {
        errorMsg = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMsg = data.detail.map((err) => `${err.loc.join('.')}: ${err.msg}`).join(', ');
      }
    }
    throw new Error(errorMsg);
  }

  return data;
}

export const authAPI = {
  login: (username, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  getMe: () => request('/auth/me'),
  createUser: (userData) =>
    request('/auth/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    }),
};

export const productsAPI = {
  getPublicProducts: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    });
    const queryString = query.toString();
    return request(`/public/products${queryString ? `?${queryString}` : ''}`);
  },
  getPublicCategories: () => request('/public/categories'),
  getPublicProductDetail: (id) => request(`/public/products/${id}`),

  getProducts: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    });
    const queryString = query.toString();
    return request(`/products${queryString ? `?${queryString}` : ''}`);
  },
  getProductDetail: (id) => request(`/products/${id}`),

  createProduct: (productData) =>
    request('/products', {
      method: 'POST',
      body: JSON.stringify(productData),
    }),
  updateProduct: (id, productData) =>
    request(`/products/${id}`, {
      method: 'PUT',
      body: JSON.stringify(productData),
    }),
  deleteProduct: (id) =>
    request(`/products/${id}`, {
      method: 'DELETE',
    }),
  uploadProductImage: async (file) => {
    const token = getAuthToken();
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/products/upload-image`, {
      method: 'POST',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(data?.detail || 'Không thể tải ảnh lên');
    }
    return data;
  },
  getCategories: () => request('/categories'),
  createCategory: (catData) =>
    request('/categories', {
      method: 'POST',
      body: JSON.stringify(catData),
    }),
  updateCategory: (id, catData) =>
    request(`/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(catData),
    }),
  deleteCategory: (id) =>
    request(`/categories/${id}`, {
      method: 'DELETE',
    }),
};

export const customersAPI = {
  getCustomers: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    });
    const queryString = query.toString();
    return request(`/customers${queryString ? `?${queryString}` : ''}`);
  },
  getMyProfile: () => request('/customers/me'),
  getCustomerDetail: (id) => request(`/customers/${id}`),
  createCustomer: (customerData) =>
    request('/customers', {
      method: 'POST',
      body: JSON.stringify(customerData),
    }),
  updateCustomer: (id, customerData) =>
    request(`/customers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(customerData),
    }),
};

export const ordersAPI = {
  getOrders: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    });
    const queryString = query.toString();
    return request(`/orders${queryString ? `?${queryString}` : ''}`);
  },
  getWorkflowCounts: () => request('/orders/workflow-counts'),
  getOrderDetail: (id) => request(`/orders/${id}`),
  createOrder: (orderData) =>
    request('/orders', {
      method: 'POST',
      body: JSON.stringify(orderData),
    }),
  approveOrder: (id) =>
    request(`/orders/${id}/approve`, {
      method: 'POST',
    }),
  rejectOrder: (id, reason = 'Đơn hàng bị Admin từ chối') =>
    request(`/orders/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  processOrder: (id) =>
    request(`/orders/${id}/process`, {
      method: 'POST',
    }),
  completeOrder: (id) =>
    request(`/orders/${id}/complete`, {
      method: 'POST',
    }),
  cancelOrder: (id, reason = 'Khách yêu cầu hủy đơn') =>
    request(`/orders/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  customerCancelOrder: (id, reason = 'Khách hàng tự hủy đơn') =>
    request(`/orders/${id}/customer-cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  forceAction: (id, payload) =>
    request(`/orders/${id}/force-action`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  claimOrder: (id, note) =>
    request(`/orders/${id}/claim`, {
      method: 'POST',
      body: JSON.stringify(note ? { note } : {}),
    }),
  reassignOrder: (id, newStaffId, reason) =>
    request(`/orders/${id}/reassign`, {
      method: 'POST',
      body: JSON.stringify({ new_staff_id: newStaffId, reason }),
    }),
  notifyTransfer: (id, payload = {}) =>
    request(`/orders/${id}/notify-transfer`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  verifyPayment: (id, payload = {}) =>
    request(`/orders/${id}/verify-payment`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  confirmCodPayment: (id, note) =>
    request(`/orders/${id}/confirm-cod-payment`, {
      method: 'POST',
      body: JSON.stringify(note ? { note } : {}),
    }),
  updateFulfillment: (id, fulfillmentStatus, note) =>
    request(`/orders/${id}/update-fulfillment`, {
      method: 'POST',
      body: JSON.stringify({ fulfillment_status: fulfillmentStatus, note }),
    }),
  confirmReturn: (id, reason, note) =>
    request(`/orders/${id}/confirm-return`, {
      method: 'POST',
      body: JSON.stringify({ reason, note }),
    }),
  requestRefund: (id, reason) =>
    request(`/orders/${id}/request-refund`, {
      method: 'POST',
      body: JSON.stringify(reason ? { reason } : {}),
    }),
  confirmRefund: (id, refundRef, reason) =>
    request(`/orders/${id}/confirm-refund`, {
      method: 'POST',
      body: JSON.stringify({ refund_reference: refundRef, reason }),
    }),
  getAuditLogs: (id) => request(`/orders/${id}/audit-logs`),
};

export const purchasesAPI = {
  getPurchases: () => request('/purchases'),
  getPurchaseDetail: (id) => request(`/purchases/${id}`),
  createPurchase: (purchaseData) =>
    request('/purchases', {
      method: 'POST',
      body: JSON.stringify(purchaseData),
    }),
};

export const inventoryAPI = {
  getLogs: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    });
    const queryString = query.toString();
    return request(`/inventory/logs${queryString ? `?${queryString}` : ''}`);
  },
  getLowStockAlerts: () => request('/inventory/low-stock'),
};

export const reportsAPI = {
  getSummary: () => request('/reports/summary'),
  getRevenueTrend: (days = 7) => request(`/reports/revenue-trend?days=${days}`),
  getTopProducts: (limit = 5) => request(`/reports/top-products?limit=${limit}`),
  exportCSV: async () => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE}/reports/export/csv`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!response.ok) throw new Error('Không thể tải file CSV');
    return await response.blob();
  },
  exportExcel: async () => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE}/reports/export/excel`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!response.ok) throw new Error('Không thể tải file Excel');
    return await response.blob();
  },
};

export const aiAPI = {
  getProviders: () => request('/ai/providers'),
  recommend: (query, budget = null, limit = 5, provider = null) =>
    request('/ai/recommend', {
      method: 'POST',
      body: JSON.stringify({ query, budget: budget ? Number(budget) : null, limit: Number(limit) || 5, ...(provider ? { provider } : {}) }),
    }),
  generateSalesReport: (period = 'month', provider = null) =>
    request('/ai/sales-report', {
      method: 'POST',
      body: JSON.stringify({ period, ...(provider ? { provider } : {}) }),
    }),
  salesQA: (query, provider = null) =>
    request('/ai/sales-qa', {
      method: 'POST',
      body: JSON.stringify({ query, ...(provider ? { provider } : {}) }),
    }),
  getLogs: (limit = 50) => request(`/ai/logs?limit=${limit}`),
  syncVectorIndex: () =>
    request('/ai/sync-index', {
      method: 'POST',
    }),
  imageSearch: async (file, limit = 5, provider = 'local') => {
    const token = getAuthToken();
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/ai/image-search?limit=${limit}&provider=${provider}`, {
      method: 'POST',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(data?.detail || 'Không thể tìm kiếm bằng hình ảnh');
    }
    return data;
  },
};
