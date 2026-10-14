// Minimal org.freedesktop.systemd1 D-Bus stub for FreeBSD jails.
// Registers the systemd bus name so unifi-core's service watcher can connect
// without throwing an unhandledRejection that shuts down the process.
'use strict';

const dbus = require('/usr/share/unifi-core/app/node_modules/@jellybrick/dbus-next');
const { Message, MessageType, MessageFlag } = dbus;

const MANAGER_PATH = '/org/freedesktop/systemd1';
const UNIT_PREFIX = '/org/freedesktop/systemd1/unit/';

const MANAGER_INTROSPECT = `<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.freedesktop.systemd1.Manager">
    <method name="Subscribe"/>
    <method name="Unsubscribe"/>
    <method name="GetUnit">
      <arg direction="in" name="name" type="s"/>
      <arg direction="out" name="unit" type="o"/>
    </method>
    <method name="LoadUnit">
      <arg direction="in" name="name" type="s"/>
      <arg direction="out" name="unit" type="o"/>
    </method>
    <method name="ListUnits">
      <arg direction="out" name="units" type="a(ssssssouso)"/>
    </method>
    <signal name="UnitNew">
      <arg name="id" type="s"/>
      <arg name="unit" type="o"/>
    </signal>
    <signal name="UnitRemoved">
      <arg name="id" type="s"/>
      <arg name="unit" type="o"/>
    </signal>
  </interface>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get">
      <arg direction="in" name="interface_name" type="s"/>
      <arg direction="in" name="property_name" type="s"/>
      <arg direction="out" name="value" type="v"/>
    </method>
    <method name="GetAll">
      <arg direction="in" name="interface_name" type="s"/>
      <arg direction="out" name="properties" type="a{sv}"/>
    </method>
  </interface>
  <interface name="org.freedesktop.DBus.Introspectable">
    <method name="Introspect">
      <arg direction="out" name="xml_data" type="s"/>
    </method>
  </interface>
</node>`;

const UNIT_INTROSPECT = `<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.freedesktop.systemd1.Unit">
    <property name="Id" type="s" access="read"/>
    <property name="Description" type="s" access="read"/>
    <property name="LoadState" type="s" access="read"/>
    <property name="ActiveState" type="s" access="read"/>
    <property name="SubState" type="s" access="read"/>
    <property name="FragmentPath" type="s" access="read"/>
  </interface>
  <interface name="org.freedesktop.systemd1.Service">
    <property name="Type" type="s" access="read"/>
    <property name="MainPID" type="u" access="read"/>
    <property name="ExecMainStatus" type="i" access="read"/>
  </interface>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get">
      <arg direction="in" name="interface_name" type="s"/>
      <arg direction="in" name="property_name" type="s"/>
      <arg direction="out" name="value" type="v"/>
    </method>
    <method name="GetAll">
      <arg direction="in" name="interface_name" type="s"/>
      <arg direction="out" name="properties" type="a{sv}"/>
    </method>
  </interface>
  <interface name="org.freedesktop.DBus.Introspectable">
    <method name="Introspect">
      <arg direction="out" name="xml_data" type="s"/>
    </method>
  </interface>
</node>`;

// Unit property stubs
const UNIT_PROPS = {
  'org.freedesktop.systemd1.Unit': {
    'Id': new dbus.Variant('s', 'stub.service'),
    'Description': new dbus.Variant('s', 'Stub unit'),
    'LoadState': new dbus.Variant('s', 'loaded'),
    'ActiveState': new dbus.Variant('s', 'active'),
    'SubState': new dbus.Variant('s', 'running'),
    'FragmentPath': new dbus.Variant('s', ''),
  },
  'org.freedesktop.systemd1.Service': {
    'Type': new dbus.Variant('s', 'simple'),
    'MainPID': new dbus.Variant('u', 1),
    'ExecMainStatus': new dbus.Variant('i', 0),
  },
};

async function main() {
  const bus = dbus.sessionBus({
    busAddress: process.env.DBUS_SYSTEM_BUS_ADDRESS || 'unix:path=/var/run/dbus/system_bus_socket',
  });

  // Wait for bus to be ready (it connects asynchronously)
  await new Promise((resolve) => {
    if (bus.name) { resolve(); return; }
    bus.once('connect', resolve);
    setTimeout(resolve, 500);
  });

  // Request the systemd1 bus name
  await bus.requestName('org.freedesktop.systemd1');
  console.log('[systemd-stub] Registered org.freedesktop.systemd1');

  // Handle all incoming method calls with stub responses
  bus.addMethodHandler((msg) => {
    if (msg.type !== MessageType.METHOD_CALL) return false;
    if (msg.flags & MessageFlag.NO_REPLY_EXPECTED) return true;

    const member = msg.member || '';
    const iface = msg.interface || '';
    const path = msg.path || '';
    const isUnit = path.startsWith(UNIT_PREFIX) || (path !== MANAGER_PATH && path !== '/');

    let body = [];
    let signature = '';

    if (member === 'Subscribe' || member === 'Unsubscribe') {
      // void
    } else if (member === 'GetUnit' || member === 'LoadUnit') {
      const name = (msg.body && msg.body[0]) || 'stub';
      const safe = name.replace(/[^a-zA-Z0-9]/g, '_');
      signature = 'o';
      body = [UNIT_PREFIX + safe];
    } else if (member === 'ListUnits') {
      signature = 'a(ssssssouso)';
      body = [[]];
    } else if (member === 'Get' && iface === 'org.freedesktop.DBus.Properties') {
      const propIface = (msg.body && msg.body[0]) || '';
      const propName = (msg.body && msg.body[1]) || '';
      signature = 'v';
      if (isUnit && UNIT_PROPS[propIface] && UNIT_PROPS[propIface][propName]) {
        body = [UNIT_PROPS[propIface][propName]];
      } else {
        body = [new dbus.Variant('s', 'active')];
      }
    } else if (member === 'GetAll' && iface === 'org.freedesktop.DBus.Properties') {
      const propIface = (msg.body && msg.body[0]) || '';
      signature = 'a{sv}';
      if (isUnit && UNIT_PROPS[propIface]) {
        body = [UNIT_PROPS[propIface]];
      } else {
        body = [{}];
      }
    } else if (member === 'Introspect') {
      signature = 's';
      body = [isUnit ? UNIT_INTROSPECT : MANAGER_INTROSPECT];
    } else {
      // Unknown method — return empty reply to avoid timeout
    }

    const reply = Message.newMethodReturn(msg);
    reply.signature = signature;
    reply.body = body;
    bus.send(reply);
    return true;
  });
}

main().catch(err => {
  console.error('[systemd-stub] Fatal:', err.message);
  process.exit(1);
});
