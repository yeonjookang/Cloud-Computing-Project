from PyInquirer import prompt
from docker import DockerClient
import subprocess

def build(client: DockerClient | None):
    questions = [
        {
            'type': 'input',
            'name': 'context',
            'message': 'Enter the build context (path or URL):'
        },
        {
            'type': 'input',
            'name': 'tag',
            'message': 'Enter the tag for the image (e.g., repository:tag):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'dockerfile',
            'message': 'Enter the path to the Dockerfile (optional):',
            'default': 'Dockerfile'
        },
        # 추가적인 빌드 옵션들은 여기에 포함될 수 있습니다.
    ]
    answers = prompt(questions)

    try:
        build_command = ['docker', 'build']
        
        # Dockerfile 지정
        if answers['dockerfile']:
            build_command.extend(['-f', answers['dockerfile']])
        
        # 태그 추가
        if answers['tag']:
            build_command.extend(['-t', answers['tag']])
        
        # 빌드 컨텍스트 추가
        build_command.append(answers['context'])

        # Docker 빌드 명령어 실행
        subprocess.run(build_command)

    except Exception as e:
        print(f"Build error: {e}")