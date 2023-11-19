import argparse
import docker
from commands.exec import exec
from commands.ps import ps
from commands.run import run
from commands.push import push
from commands.pull import pull
from commands.build import build

COMMANDS = {
    'RUN': 'run',
    'EXEC': 'exec',
    'BUILD': 'build',
    'PUSH': 'push',
    'PULL' : 'pull',
    'PS': 'ps'
}


def main():
    try:
        client = docker.from_env()
    except:
        client = None

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    run_parser = subparsers.add_parser(
        COMMANDS['RUN'], help='Create Container')
    push_parser = subparsers.add_parser(
        COMMANDS['PUSH'], help='image push')
    pull_parser = subparsers.add_parser(
        COMMANDS['PULL'], help='image pull')
    exec_parser = subparsers.add_parser(
        COMMANDS['EXEC'], help='Execute a command in a running container')
    ps_parser = subparsers.add_parser(
        COMMANDS['PS'], help='List containers')

    args = parser.parse_args()

    if args.command == COMMANDS['RUN']:
        run(client)
    elif args.command == COMMANDS['PUSH']:
        push(client)
    elif args.command == COMMANDS['PULL']:
        pull(client)
    elif args.command == COMMANDS['BUILD']:
        build(client)
    elif args.command == COMMANDS['EXEC']:
        exec(client)
    elif args.command == COMMANDS['PS']:
        ps(client)

if __name__ == '__main__':
    main()
