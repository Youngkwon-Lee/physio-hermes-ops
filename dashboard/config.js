// 배포 환경별 API endpoint 오버라이드용 설정 파일
// - 로컬 기본값: http://127.0.0.1:8788
// - Vercel/외부 배포 시 여기에 공개 가능한 read-only API endpoint를 넣어 사용
//   예) window.NAUTILUS_CONFIG = { opsApiBaseUrl: 'https://ops-api.example.com' };
window.NAUTILUS_CONFIG = window.NAUTILUS_CONFIG || {
  // opsApiBaseUrl: 'https://ops-api.example.com'
};
