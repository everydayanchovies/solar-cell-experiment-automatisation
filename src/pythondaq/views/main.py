import click

from pythondaq.controllers.meta_manager import MetaManager


@click.group()
def cmd_group():
    pass


@cmd_group.command("list")
@click.option(
    "-s",
    "--search",
    default="",
    help="Filter the list of ports to the specified query",
    show_default=True,
    type=click.STRING
)
def ls(search):
    if not search:
        print("The following devices are connected to your computer:")
    else:
        print(f"The following devices match '{search}'")

    [print(p) for p in MetaManager().list_devices() if not search or search.lower() in p.lower()]


@cmd_group.command()
@click.argument("search_arg", type=click.STRING, required=False)
@click.option(
    "-s",
    "--search",
    default="",
    help="Try to pin down one device matching the specified search query",
    show_default=True,
    type=click.STRING
)
def info(search, search_arg):
    q = search if search else search_arg
    if not q:
        return print("Please specify which device to communicate with. For example: 'diode info arduino'")

    meta_man = MetaManager()

    devices = meta_man.list_devices()
    devices = [p for p in devices if q.lower() in p.lower()]

    if not devices:
        return print("No devices found for your search query, try searching less specifically")

    if len(devices) > 1:
        print(f"Your query yielded {len(devices)} devices. Please specify a single device.")
        return [print(p) for p in devices]

    print(meta_man.info(devices[0]))


if __name__ == "__main__":
    cmd_group()
