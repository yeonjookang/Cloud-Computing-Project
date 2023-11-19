# 기본 이미지 설정
FROM ubuntu:latest

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일 복사
COPY . /app

# 의존성 설치
RUN apt-get update && apt-get install -y python3

# 실행 명령어 설정
CMD ["python3", "app.py"]