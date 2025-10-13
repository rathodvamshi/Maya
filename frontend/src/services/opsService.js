// frontend/src/services/opsService.js
import apiClient from './api';

const opsService = {
  async health() {
    const { data } = await apiClient.get('/ops/health');
    return data;
  },
  async listScheduled() {
    const { data } = await apiClient.get('/ops/list_scheduled_tasks');
    return data;
  },
  async revoke(taskId) {
    const { data } = await apiClient.post(`/ops/revoke`, null, { params: { task_id: taskId } });
    return data;
  },
  async inspect() {
    const { data } = await apiClient.get('/ops/celery_inspect');
    return data;
  },
};

export default opsService;
