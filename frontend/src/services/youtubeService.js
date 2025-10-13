// frontend/src/services/youtubeService.js
import apiClient from './api';

export async function searchYouTube(query, opts = {}) {
  const params = { q: query, max_results: Math.min(Math.max(opts.maxResults || 5, 1), 10) };
  if (opts.regionCode && typeof opts.regionCode === 'string' && opts.regionCode.length === 2) {
    params.region_code = opts.regionCode;
  }
  const res = await apiClient.get('/youtube/search', { params });
  return res.data; // { items, top }
}

export default { searchYouTube };
