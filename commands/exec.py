from __future__ import print_function, unicode_literals
from PyInquirer import style_from_dict, Token, prompt, Separator
from pprint import pprint
from docker import DockerClient
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

def exec(client: DockerClient | None):
    questions = [
        {
            'type': 'input',
            'name': 'container_name',
            'message': 'Enter the name or ID of the container:'
        },
        {
            'type': 'confirm',
            'name': 'interactive',
            'message': 'Do you want to keep STDIN open and allocate a pseudo-TTY (interactive mode)?',
            'default': False
        },
        {
            'type': 'input',
            'name': 'command',
            'message': 'Enter the command you want to execute:'
        },
        {
            'type': 'input',
            'name': 'workdir',
            'message': 'Enter the working directory (optional):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'user',
            'message': 'Enter the username or UID (optional):',
            'default': ''
        },
        # Add more options here as required
        {
            'type': 'confirm',
            'name': 'detach',
            'message': 'Do you want to run the command in the background (detached mode)?',
            'default': False
        },
        {
            'type': 'input',
            'name': 'env_vars',
            'message': 'Enter any environment variables (comma-separated key=value pairs, e.g., VAR1=value1,VAR2=value2):',
            'default': ''
        }
    ]
    answers = prompt(questions)

    try:
        if answers['interactive'] and answers['command'] == 'bash':
            subprocess.run(['docker', 'exec', '-it', answers['container_name'], 'bash'])
        else:
            # ... [기존 exec_run 사용 코드] ...
            # Prepare environment variables
            env_vars = answers['env_vars'].split(',') if answers['env_vars'] else None

            container = client.containers.get(answers['container_name'])
            exec_instance = container.exec_run(
                cmd=answers['command'],
                environment=env_vars,
                detach=answers['detach']
            )

            # Fetching output for non-detached mode
            if not answers['detach']:
                print(exec_instance.output.decode("utf-8"))
        

    except Exception as e:
        print(f"API error: {e}")
