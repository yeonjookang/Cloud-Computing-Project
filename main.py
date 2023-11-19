import argparse
import docker
from commands.exec import exec
from commands.ps import ps
from commands.run import run

COMMANDS = {
    'ADD': 'add',  # example
    'RUN': 'run',
    'EXEC': 'exec',
    'BUILD': 'build',
    'PS': 'ps'
}


def main():
    try:
        client = docker.from_env()
    except:
        client = None

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser(COMMANDS['ADD'], help='Add two numbers')
    add_parser.add_argument('num1', type=int)
    add_parser.add_argument('num2', type=int)

    run_parser = subparsers.add_parser(
        COMMANDS['RUN'], help='Create Container')

    exec_parser = subparsers.add_parser(
        COMMANDS['EXEC'], help='Execute a command in a running container')
    # exec_parser.add_argument('container_id', type=str)

    ps_parser = subparsers.add_parser(
        COMMANDS['PS'], help='List containers')

    args = parser.parse_args()

    if args.command == COMMANDS['ADD']:
        result = args.num1 + args.num2
        print(f'The sum is: {result}')
    elif args.command == COMMANDS['RUN']:
        run(client)
    elif args.command == COMMANDS['EXEC']:
        # print(f'exec container id {args.container_id}')
        exec(client)
    elif args.command == COMMANDS['PS']:
        # print(f'exec container id {args.container_id}')
        ps(client)


if __name__ == '__main__':
    main()
