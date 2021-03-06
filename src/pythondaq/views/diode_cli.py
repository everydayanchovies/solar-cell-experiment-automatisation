from typing import Union
from rich import print
from rich.progress import Progress

import click

from pythondaq.models.diode_experiment import list_devices, device_info, DiodeExperiment, save_data_to_csv, \
    plot_current_against_voltage


def port_for_search_query(search_q) -> Union[str, None]:
    """
    Tries to retrieve a port for a given search query.
    :param search_q: a string by which to filter the available ports
    :return: either a single matching port or nothing
    """
    matching_devices = list_devices(search_q)

    if not matching_devices:
        print("No devices found for your search query, try searching less specifically")
        return None

    if len(matching_devices) > 1:
        print(f"Your query yielded {len(matching_devices)} devices. Please specify a single device.")
        [print(d) for d in matching_devices]
        return None

    return matching_devices[0]


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
    """
    Command with which to list the available devices.
    :param search: filters the available devices by this string
    """
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
    """
    Shows the info of a requested device.
    :param search: filters the available devices by this string
    :param search_arg: see search
    """
    q = search if search else search_arg
    if not q:
        return print("Please specify which device to communicate with. For example: 'diode info arduino'")

    print(device_info(port_for_search_query(q)))


@cmd_group.command()
@click.option(
    "-u",
    "--voltage",
    default=0.0,
    help="Set the output voltage before taking the measurement",
    show_default=True,
    type=click.FloatRange(0, 3.3),
    required=False
)
@click.option(
    "-p",
    "--port",
    help="The port of the Arduino device (can be a partial string)",
    type=click.STRING,
    required=True
)
@click.option(
    "-r",
    "--repeat",
    help="Amount of times to repeat the measurement",
    type=click.INT,
    required=False,
    default=1,
)
def measure(port, voltage, repeat):
    """
    Measures the current running through the LED and sets the output voltage prior to that.
    """
    port = port_for_search_query(port)
    if not port:
        return

    if voltage:
        print(f"V_out has been set to {voltage} V.")

    _, (i, i_err) = DiodeExperiment(port).measure_led(voltage, repeat)
    if repeat > 1:
        print(f"The current running through the LED is {i:.6f}??{i_err:.6f} A.")
    else:
        print(f"The current running through the LED is {i:.6f} A.")


@cmd_group.command()
@click.option(
    "-p",
    "--port",
    help="The port of the Arduino device (can be a partial string)",
    type=click.STRING,
    required=True
)
@click.option(
    "-a",
    "--start",
    help="Set the starting voltage of the measurement",
    type=click.FloatRange(0, 3.3),
    required=False,
    default=0.0,
)
@click.option(
    "-b",
    "--end",
    help="Set the ending voltage of the measurement",
    type=click.FloatRange(0, 3.3),
    required=False,
    default=3.3,
)
@click.option(
    "-s",
    "--step",
    help="Set the step size of the measurement",
    type=click.FloatRange(0, 3.3),
    required=True,
)
@click.option(
    "-o",
    "--output",
    help="The file in which to save the measurement",
    required=False,
    default=None,
)
@click.option(
    "-r",
    "--repeat",
    help="Amount of times to repeat the measurement",
    type=click.INT,
    required=False,
    default=1,
)
@click.option(
    "-g",
    "--graph",
    help="Plot the measurement",
    is_flag=True,
)
def scan(port, start, end, step, output, repeat, graph):
    """
    Takes a series of measurements while varying the output voltage.
    """
    port = port_for_search_query(port)
    if not port:
        return

    m = DiodeExperiment(port)

    rows = []
    with Progress() as progress:
        task = progress.add_task("Gathering measurements...", total=(end - start))

        for ((u, u_err), (i, i_err)) in m.scan_led(start, end, step, repeat):
            rows.append((u, u_err, i, i_err))
            if repeat > 1:
                print(f"{u:.3f}??{u_err:.3f} V\t{i:.6f}??{i_err:.6f} A")
            else:
                print(f"{u:.3f} V\t{i:.6f} A")

            progress.update(task, advance=step)

    if output:
        save_data_to_csv(output, ["U", "U_err", "I", "I_err"], rows)

    if graph:
        u, u_err, i, i_err = zip(*rows)
        plot_current_against_voltage(u, u_err, i, i_err)


if __name__ == "__main__":
    cmd_group()
