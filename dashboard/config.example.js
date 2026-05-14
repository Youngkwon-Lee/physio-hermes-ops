// 공개 배포용 예시 설정 파일
// 사용법:
// 1) 이 파일을 복사해 dashboard/config.js로 저장
// 2) 아래 opsApiBaseUrl을 실제 공개 API endpoint로 변경
// 3) 토큰은 절대 하드코딩하지 말고 브라우저에서 직접 입력
window.NAUTILUS_CONFIG = {
  // 예: Cloudflare Tunnel / Reverse Proxy / API Gateway
  opsApiBaseUrl: 'https://ops-api.example.com'
};
