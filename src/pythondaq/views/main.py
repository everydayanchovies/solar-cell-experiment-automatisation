import click

from pythondaq.models.diode_experiment import list_devices, device_info, measure_current_through_led


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

    [print(d) for d in list_devices(search)]


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

    res = device_info(q)

    if not res:
        return print("No devices found for your search query, try searching less specifically")

    if type(res) is list:
        print(f"Your query yielded {len(res)} devices. Please specify a single device.")
        return [print(d) for d in res]

    print(res)


@cmd_group.command()
@click.option(
    "-u",
    "--voltage",
    default=0.0,
    help="Set the output voltage before taking the measurement",
    show_default=True,
    type=click.FloatRange(0,3.3)
)
def measure(voltage):
    current = measure_current_through_led(voltage)


if __name__ == "__main__":
    cmd_group()
