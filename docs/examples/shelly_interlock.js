// Pool Control - hardware interlock and watchdog for a Shelly Pro 3
// (Gen2 scripting).
//
// Interlock: switches off the chlorinator and the dosing pump as soon as the
// filter pump stops and prevents them from being switched on while the pump
// is off.
//
// Watchdog: checks every minute whether Home Assistant is reachable. After
// WATCHDOG_FAILURES failed checks the chlorinator and the dosing pump are
// switched off. The filter pump keeps running (limited by its auto-off).
// Set HA_URL to "" to disable the watchdog.
//
// Adjust the channel numbers (0-based) and the settings to your setup. Create
// a long-lived access token in Home Assistant (profile > security).

let PUMP = 0; // switch:0 filter pump
let DEPENDENT = [1, 2]; // switch:1 chlorinator, switch:2 pH dosing pump

let HA_URL = "http://homeassistant.local:8123/api/";
let HA_TOKEN = "PASTE_LONG_LIVED_ACCESS_TOKEN";
let WATCHDOG_INTERVAL_MS = 60 * 1000;
let WATCHDOG_FAILURES = 5;

let failures = 0;

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

function watchdogResult(result, errorCode) {
  if (errorCode === 0 && result && result.code === 200) {
    failures = 0;
    return;
  }
  failures++;
  if (failures === WATCHDOG_FAILURES) {
    print("Home Assistant unreachable, switching off chlorinator and dosing pump");
    for (let i = 0; i < DEPENDENT.length; i++) {
      switchOff(DEPENDENT[i]);
    }
  }
}

if (HA_URL !== "") {
  Timer.set(WATCHDOG_INTERVAL_MS, true, function () {
    Shelly.call(
      "HTTP.Request",
      {
        method: "GET",
        url: HA_URL,
        headers: { Authorization: "Bearer " + HA_TOKEN },
        timeout: 10,
      },
      watchdogResult
    );
  });
}
