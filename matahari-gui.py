#!/usr/bin/python
# matahari-gui.py - GUI for matahari
_COPYRIGHT = "Copyright (c) 2012 Red Hat, Inc."
_AUTHORS = ["Roman Rakus <rrakus@redhat.com>"]
_LICENSE = \
"""This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA."""
_VERSION = "0.0.1"

from gi.repository import Gtk
from gi.repository import GObject
import os
import qmf.console as qc
import uuid
from ast import literal_eval

class MyQmfClass(GObject.GObject):
    def __init__(self, qmf_object):
        """
        Init class with provided qmfobject, which is got from
        qmf.session.getObjects
        """
        GObject.GObject.__init__(self)
        self.qmf_object = qmf_object

# Got from qpid/managementdata.py
# Any array or dict? hmmmpf
QPIDTYPES = [
None,
"uint8",
"uint16",
"uint32",
"uint64",
"bool",
"short-string",
"long-string",
"abs-time",
"delta-time",
"reference",
"boolean",
"float",
"double",
"uuid",
"field-table",
"int8",
"int16",
"int32",
"int64",
"object",
"list",
"array"
]

QPIDTYPESCONV = {
"uint8" : int,
"uint16" : int,
"uint32" : int,
"uint64" : int,
"bool" : bool,
"short-string" : str,
"long-string" : str,
"boolean" : bool,
"float" : float,
"double" : float,
"uuid" : uuid.UUID,
"field-table" : dict,
"int8" : int,
"int16" : int,
"int32" : int,
"int64" : int,
"list" : list,
"array" : list,
}

class MainWindow:
    """
    Main window
    """
    def __init__(self):
        builder = Gtk.Builder()
        self.builder = builder
        if os.access("./matahari-gui.ui", os.F_OK):
            builder.add_from_file ("./matahari-gui.ui")
        else:
            builder.add_from_file (
                "/usr/share/matahari-gui/matahari-gui.ui")
        builder.connect_signals(self)

        self.main_window = builder.get_object("Main Window")
        self.entry_host = builder.get_object("entry_host")
        self.spinbutton_port = builder.get_object("spinbutton_port")
        self.label_broker = builder.get_object("label_broker")
        self.treestore_agents = builder.get_object("treestore_agents")
        self.treeview_agents = builder.get_object("treeview_agents")


        # Call method dialog
        self.cmd = builder.get_object("dialog_call_method")
        self.cmd_lsa = builder.get_object("liststore_arguments")
        self.cmd_tva = builder.get_object("treeview_arguments")
        self.cmd_ot = builder.get_object("label_obj_type")
        self.cmd_mn = builder.get_object("label_method_name")
        self.cmd_ls = builder.get_object("label_status")

        self.main_window.resize(700, 500)
        self.cmd.resize(400, 300)

        self._broker = None
        self._session = None

        self._agents = []
        self.selected_object = None
        # Tree store types
        # TYPE : handler
        self.TSTYPES = {
           "object": None,
           "property": None,
           "method": self.call_method}

    def show_about(self, *args):
        about = Gtk.AboutDialog()
        about.set_authors(_AUTHORS)
        about.set_copyright(_COPYRIGHT)
        about.set_license(_LICENSE)
        about.set_program_name("Matahari GUI")
        about.set_version(_VERSION)
        about.run()
        about.hide()

    def run(self):
        """
        start the main application
        """
        self.main_window.show_all()
        Gtk.main()

    def destroy(self, *args):
        """
        end
        """
        self._disconnect()
        Gtk.main_quit()

    def _disconnect(self):
        """Disconnect and close session"""
        if self._session:
            if self._broker:
                self._session.delBroker(self._broker)
            self._broker = None
            self._session.close()
            self._session = None

    def call_method(self, mqo, method):
        qo = mqo.qmf_object
        qo_methods = qo.getMethods()
        mname = method.split("(")[0]
        for i, m in enumerate(qo_methods):
            if str(m) == method:
                arguments = qo_methods[i].arguments
        self.cmd_fill(qo.getClassKey().getClassName(), mname, arguments)
        self.selected_object = qo
        self.cmd.show_all()

    def cmd_fill(self, obj_type, method, arguments):
        """fill call method dialog with class name, method name and qpid args
        """
        self.cmd_ot.set_text(obj_type)
        self.cmd_mn.set_text(method)
        self.cmd_lsa.clear()
        self.cmd_ls.set_text("")

        for arg in arguments:
            self.cmd_lsa.append([arg.name, arg.dir, QPIDTYPES[arg.type],
                "", "I" in arg.dir])

    def arg_edited(self, renderer, path, new_text, *data):
        self.cmd_lsa.set_value(self.cmd_tva.get_model().get_iter(path), 3,
            new_text)

    def refill_treestore(self):
        self.treestore_agents.clear()
        for agent in self._agents:
            for klass in self._session.getClasses("org.matahariproject"):
                if (klass.type != "_event" and klass.cname != "Agent"):
                    objs = self._session.getObjects(_class=klass.cname,
                        _agent=agent._agent, _package="org.matahariproject")
                    for obj in objs:
                        mqo = MyQmfClass(obj)
                        # Root leaf of tree - class name
                        treeiter = self.treestore_agents.append(None,
                            [klass.cname, agent.hostname, mqo, "object"])
                        # leaf of a class, properties
                        for (pname, pvalue) in obj.getProperties():
                            self.treestore_agents.append(treeiter,
                                [str(pname), str(pvalue), mqo, "property"])
                        # leaf of a class, methods
                        for name in obj.getMethods():
                            self.treestore_agents.append(treeiter,
                                [str(name), str(name.desc), mqo, "method"])


    def _connect(self, host, port):
        """
        Connect to broker
        """
        addr = 'amqp://%(host)s:%(port)u' % {'host': host, 'port': port}
        self._session = qc.Session()
        self._broker = self._session.addBroker(addr)
        print self._broker
        self.label_broker.set_text("%(host)s:%(port)s" %{
                                   "host" : self._broker.host,
                                   "port" : str(self._broker.port)})
        self._agents = self._session.getObjects(_class="Agent",
                                                _package="org.matahariproject")
        self.refill_treestore()

    def connect_clicked(self, *args):
        """
        We want to connect to some broker
        """
        self._connect(
            self.entry_host.get_text(), int(self.spinbutton_port.get_text()))

    def toggled(self, renderer, index):
        """Toggled state of selection of one of agent"""
        self.toggle_selected(renderer, index)

    def toggle_selected(self, renderer, index):
        self.liststore_agents[index][0] = not self.liststore_agents[index][0]

    def row_activated(self, tree_view, path, column, *args):
        model = tree_view.get_model()
        tv_iter = model.get_iter(path)
        (ts_name, ts_value, ts_ref, ts_type) = model[tv_iter]
        handler = self.TSTYPES[ts_type]
        if handler is not None:
            handler(ts_ref, ts_name)

    def cmd_close(self, *args):
        """close/hide call method dialog"""
        self.cmd.hide()
        return True

    def cmd_execute(self, *args):
        """execute method with specified arguments"""
        lmargs = [] # method arguments list
        for n, row in enumerate(self.cmd_lsa):
            if "I" in row[1]:
                try:
                    evaled = literal_eval(row[3])
                    conved = QPIDTYPESCONV[row[2]](evaled)
                except:
                    self.cmd_ls.set_text(
                        "Invalid format for argument %s at line %d" %(row[0],n))
                    return
                lmargs.append(conved)
        method = getattr(self.selected_object, self.cmd_mn.get_text())
        result = method(*lmargs)
        print 20 * "-"
        print result
        for row in self.cmd_lsa:
            if row[0] in result.outArgs:
                row[3] = str(result.outArgs[row[0]])
        self.cmd_ls.set_text("%s (%d)" % (result.text, result.status))

if __name__ == "__main__":
    MW = MainWindow()
    MW.run()
