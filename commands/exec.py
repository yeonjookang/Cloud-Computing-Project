from __future__ import print_function, unicode_literals
from PyInquirer import style_from_dict, Token, prompt, Separator
from pprint import pprint
import subprocess

style = style_from_dict({
    Token.Separator: '#cc5454',
    Token.QuestionMark: '#673ab7 bold',
    Token.Selected: '#cc5454',  # default
    
    Token.Pointer: '#673ab7 bold',
    Token.Instruction: '',  # default
    Token.Answer: '#f44336 bold',
    Token.Question: '',
})

def exec(container_id,client):
    questions = [
        {
            'type':'confirm',
            'name':'--detach',
            'message':'Do you want Detached Mode?(run command in the background)',
            'default':False
        },
        {
            'type':'confirm',
            'name':'--detach-key',
            'message':'Do you want to override the key sequence for detaching a container?',
            'default':False
        },
        {
            'type':'input',
            'name':'--detach-key arg',
            'message':'Enter the key sequence with comma: ',
            'when': lambda answers: answers['--detach']
        },
        {
            'type':'confirm',
            'name':'--env',
            'message':'Do you want to set environment variables?',
            'default':False
        },
        {
            'type':'checkbox',
            'name':'--env way',
            'message':'by file? or by input key-value string?',
            'choices':[
                {
                    'name':'file'
                },
                {
                    'name':'input key-value string'
                }
            ],
            'when': lambda answers: answers['--env']
        },
        {
            'type': 'input',
            'name': '--env file_path',
            'message': 'Enter the file path:',
            'when': lambda answers: 'file' in answers['--env way']
        },
        {
            'type': 'input',
            'name': '--env key_value',
            'message': 'Enter key-value pair:',
            'when': lambda answers: 'input key-value string' in answers['--env way']
        },
        {
            'type':'confirm',
            'name':'--interactive',
            'message':'Do you want to keep STDIN open even if not attached?',
            'default':False
        },
        {
            'type':'confirm',
            'name':'--privileged',
            'message':'Do you want to give extended privileges to the command?',
            'default':False
        },
        {
            'type':'confirm',
            'name':'--tty',
            'message':'Do you want to allocate a pseudo-TTY?',
            'default':False
        },
        {
            'type':'confirm',
            'name':'--user',
            'message':'Do you want to specify username or UID?',
            'default':False
        },
        {
            'type':'input',
            'name':'--user arg',
            'message':'Enter the username or uid: ',
            'when': lambda answers: answers['--user']
        },
        {
            'type':'confirm',
            'name':'--workdir',
            'message':'Do you want working directory inside the container?',
            'default':False
        },
        {
            'type':'input',
            'name':'--workdir arg',
            'message':'Enter the dir path: ',
            'when': lambda answers: answers['--workdir']
        }
    ]
    answers = prompt(questions, style=style)
    
    # 도커 exec 명령어 구성
    command = ['docker', 'exec']
    
    # 사용자의 선택에 따라 명령어에 옵션 추가
    if answers.get('--detach'):
        command.append('-d')
    if answers.get('--detach-key'):
        command.extend(['--detach-keys', answers['--detach-key arg']])
    if answers.get('--env'):
        if 'file' in answers['--env way']:
            command.extend(['--env-file', answers['--env file_path']])
        if 'input key-value string' in answers['--env way']:
            command.extend(['-e', answers['--env key_value']])
    if answers.get('--interactive'):
        command.append('-i')
    if answers.get('--privileged'):
        command.append('--privileged')
    if answers.get('--tty'):
        command.append('-t')
    if answers.get('--user'):
        command.extend(['-u', answers['--user arg']])
    if answers.get('--workdir'):
        command.extend(['-w', answers['--workdir arg']])
    
    # 마지막으로 컨테이너 ID 추가
    command.append(container_id)

    # 명령어 실행
    try:
        subprocess.run(command)
    except Exception as e:
        print(f"Error executing docker command: {e}")

    exec(container_id)