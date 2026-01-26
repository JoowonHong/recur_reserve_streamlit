import requests
import datetime
import pytz
#동기화 되었나?

class PixellotAPI():

    def __init__(self,isReal):
        
        if isReal ==False:
            BASE_URL = "https://api.stage.pixellot.tv/v1"  # stage API 기본 URL
            USERNAME = "yst_stage_api"
            PASSWORD = "yst4DByLQZELW7j7OWV0Mk79BIOVBs"
        elif isReal == True:
            BASE_URL = "https://api.pixellot.tv/v1" # 상용 API
            USERNAME = "yst_api"
            PASSWORD = "yst7tRTe7q7R3qFTfGvUg8TRayUuR9e"
        
        self.base_url = BASE_URL
        self.username = USERNAME
        self.password = PASSWORD
        self.token = self.get_api_token()
        self.request_body = None  

    def seoul_to_utc_iso(seoul_time_str):
        """
        서울 시간(YYYY-MM-DD HH:MM:SS) 문자열을 UTC ISO 포맷(YYYY-MM-DDTHH:MM:SS.000Z)으로 변환
        """
        seoul = pytz.timezone('Asia/Seoul')
        dt_seoul = seoul.localize(datetime.datetime.strptime(seoul_time_str, "%Y-%m-%d %H:%M:%S"))
        dt_utc = dt_seoul.astimezone(pytz.utc)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def get_api_token(self):
        """
        API에 로그인하여 토큰을 받아오는 함수.

        Args:
            base_url (str): API의 기본 URL (로그인 엔드포인트 포함).
            username (str): 로그인에 사용할 사용자 이름.
            password (str): 로그인에 사용할 비밀번호.

        Returns:
            str: 반환된 토큰 값 (성공 시).
        """
        # 로그인 엔드포인트 URL
        login_url = f"{self.base_url}/login"  # 엔드포인트 URL 수정 필요

        # 요청에 필요한 데이터
        payload = {
            "username": self.username,
            "password": self.password
        }

        try:
            # POST 요청 보내기
            response = requests.post(login_url, json=payload)

            # HTTP 응답 상태 확인
            response.raise_for_status()

            # JSON 응답에서 토큰 추출
            token = response.json().get("token")  # 'token' 키는 API 문서에 따라 수정 필요

            if not token:
                raise ValueError("토큰이 응답에 포함되지 않았습니다.")

            print("토큰을 성공적으로 받아왔습니다.")
            return token

        except requests.exceptions.RequestException as e:
            print(f"요청 중 오류 발생: {e}")
        except ValueError as e:
            print(f"응답 처리 중 오류 발생: {e}")

        return None


    def get_api_data(self,endpoint):
        """
        API에서 데이터를 가져오는 함수.

        Returns:
            dict: API 응답 데이터 (성공 시).
        """
        if not self.token:
            print("토큰이 없습니다. 먼저 로그인하세요.")
            return None

        # 요청 URL 생성
        url = f"{self.base_url}/{endpoint}"

        # 인증 헤더 설정
        headers = {
            "Authorization": self.token  # 'Bearer'는 API 문서에 따라 수정 필요
        }   
        try:
            # GET 요청 보내기
            response = requests.get(url, headers=headers)

            # HTTP 응답 상태 확인
            response.raise_for_status()

            # JSON 응답 반환
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"요청 중 오류 발생: {e}")

        return None