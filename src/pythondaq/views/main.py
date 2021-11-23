import click
import pyvisa


@click.group()
def cmd_group():
    pass


@cmd_group.command()
@click.option(
    "-s",
    "--search",
    default="",
    help="Filter the list of ports to the specified query",
    show_default=True,
    type=click.STRING
)
def ls(search):
    ports = pyvisa.ResourceManager("@Py").list_resources()
    print(ports)


if __name__ == "__main__":
    cmd_group()