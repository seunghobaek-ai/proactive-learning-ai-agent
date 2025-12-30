/**
 * 구루미 프론트엔드에서 사용할 클라이언트 코드
 * 서버의 /finish API를 호출하여 결과를 받아옴
 */

/**
 * 비동기로 최종 결과 가져오기 (async/await)
 * @param {number} time - 총 학습 시간 (초 단위) - 필수
 * @param {string} email - 사용자 이메일 (선택적)
 * @param {string} serverUrl - 멘토님 서버 URL (예: "https://멘토님서버.com")
 * @returns {Promise<Object>} JSON 응답 데이터
 */
async function fetch_final_result_async(time, email = '', serverUrl = 'http://localhost:8080') {
    try {
        let url = `${serverUrl}/finish?time=${time}`;
        if (email) {
            url += `&email=${encodeURIComponent(email)}`;
        }
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
            },
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
        
    } catch (error) {
        console.error('결과 조회 실패:', error);
        throw error;
    }
}

/**
 * 동기 방식으로 최종 결과 가져오기 (Promise.then)
 * @param {number} time - 총 학습 시간 (초 단위) - 필수
 * @param {string} email - 사용자 이메일 (선택적)
 * @param {string} serverUrl - 멘토님 서버 URL
 * @returns {Promise<Object>} JSON 응답 데이터
 */
function fetch_final_result(time, email = '', serverUrl = 'http://localhost:8080') {
    return fetch_final_result_async(time, email, serverUrl);
}

/**
 * 결과를 콘솔에 출력 (테스트용)
 * @param {number} time - 총 학습 시간 (초 단위) - 필수
 * @param {string} email - 사용자 이메일 (선택적)
 * @param {string} serverUrl - 멘토님 서버 URL
 */
function print_final_result(time, email = '', serverUrl = 'http://localhost:8080') {
    fetch_final_result_async(time, email, serverUrl)
        .then(data => {
            console.log('=== 학습 결과 ===');
            console.log(JSON.stringify(data, null, 2));
        })
        .catch(error => {
            console.error('오류:', error);
        });
}

// 사용 예시:
// const result = await fetch_final_result_async(6000);  // 이메일 없이
// const result = await fetch_final_result_async(6000, 'user@example.com');  // 이메일과 함께
// console.log(result);


