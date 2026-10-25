// Pool Control - hardware interlock for a Shelly Pro 3 (Gen2 scripting).
//
// Switches off the chlorinator and the dosing pump as soon as the filter
// pump stops and prevents them from being switched on while the pump is
// off. Works independently of Home Assistant.
//
// Adjust the channel numbers (0-based) to your wiring.

let PUMP = 0; // switch:0 filter pump
let DEPENDENT = [1, 2]; // switch:1 chlorinator, switch:2 pH dosing pump

function switchOff(id) {
  Shelly.call("Switch.Set", { id: id, on: false });
}

function enforceForDependent(id) {
  Shelly.call("Switch.GetStatus", { id: PUMP }, function (status) {
    if (status && status.output === false) {
      switchOff(id);
    }
  });
}

Shelly.addStatusHandler(function (event) {
  if (!event.delta || typeof event.delta.output === "undefined") {
    return;
  }
  if (event.component === "switch:" + JSON.stringify(PUMP) && event.delta.output === false) {
    for (let i = 0; i < DEPENDENT.length; i++) {
      switchOff(DEPENDENT[i]);
    }
    return;
  }
  for (let i = 0; i < DEPENDENT.length; i++) {
    if (event.component === "switch:" + JSON.stringify(DEPENDENT[i]) && event.delta.output === true) {
      enforceForDependent(DEPENDENT[i]);
    }
  }
});
