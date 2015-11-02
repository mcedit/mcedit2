"""
    ipython_widget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)
#
# import atexit
#
# from IPython.kernel.zmq.kernelapp import IPKernelApp
# from IPython.lib.kernel import find_connection_file
# from IPython.qt.inprocess import QtInProcessKernelManager
# from IPython.qt.console.rich_ipython_widget import RichJupyterWidget
# from IPython.utils.traitlets import TraitError
# from PySide import QtGui, QtCore
#
# def event_loop(kernel):
#     kernel.timer = QtCore.QTimer()
#     kernel.timer.timeout.connect(kernel.do_one_iteration)
#     kernel.timer.start(1000*kernel._poll_interval)
#
# def default_kernel_app():
#     app = IPKernelApp.instance()
#     app.initialize(['python', '--pylab=qt'])
#     app.kernel.eventloop = event_loop
#     return app
#
# def default_manager(kernel):
#     connection_file = find_connection_file(kernel.connection_file)
#     manager = QtInProcessKernelManager(connection_file=connection_file)
#     manager.load_connection_file()
#     atexit.register(manager.cleanup_connection_file)
#     return manager
#
# def console_widget(manager):
#     try: # Ipython v0.13
#         widget = RichJupyterWidget(gui_completion='droplist')
#     except TraitError:  # IPython v0.12
#         widget = RichJupyterWidget(gui_completion=True)
#     widget.kernel_manager = manager
#     return widget
#
# def terminal_widget(**kwargs):
#     kernel_app = default_kernel_app()
#     manager = default_manager(kernel_app)
#     widget = console_widget(manager)
#
#     #update namespace
#     kernel_app.shell.user_ns.update(kwargs)
#     client = manager.client()
#     client.start_channels()
#     widget.kernel_client = client
#
#     kernel_app.start()
#     return widget
#
# if __name__ == '__main__':
#     app = QtGui.QApplication([])
#     widget = terminal_widget(testing=123)
#     widget.show()
#     app.exec_()

import os

from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from IPython.lib import guisupport


def print_process_id():
    print('Process ID is:', os.getpid())


def terminal_widget(**kwargs):

    # Create an in-process kernel
    # >>> print_process_id()
    # will print the same process ID as the main process
    kernel_manager = QtInProcessKernelManager()
    kernel_manager.start_kernel()
    kernel = kernel_manager.kernel
    kernel.gui = 'qt4'
    kernel.shell.push(kwargs)

    kernel_client = kernel_manager.client()
    kernel_client.start_channels()

    control = RichJupyterWidget()
    control.kernel_manager = kernel_manager
    control.kernel_client = kernel_client
    return control

def main():
    # Print the ID of the main process
    print_process_id()

    app = guisupport.get_app_qt4()
    control = terminal_widget(testing=123)

    def stop():
        control.kernel_client.stop_channels()
        control.kernel_manager.shutdown_kernel()
        app.exit()

    control.exit_requested.connect(stop)

    control.show()

    guisupport.start_event_loop_qt4(app)

if __name__ == '__main__':
    main()
