/**
 * System page - display settings, hardware, and defaults.
 */

import { defineComponent } from "./vendor.js";

export default defineComponent({
  name: "HardwarePage",
  props: {
    store: { type: Object, required: true },
  },
  data() {
    return {
      timezoneBusy: false,
      timezoneStatus: "",
    };
  },
  methods: {
    async useIpTimezone() {
      this.timezoneBusy = true;
      this.timezoneStatus = "Looking up this network's time zone…";
      try {
        const response = await fetch(
          this.store.ui.urls?.ipTimezone || "/api/timezone/ip",
          { credentials: "same-origin", headers: { Accept: "application/json" } }
        );
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Lookup failed.");
        this.store.config.timezone = result.timezone;
        this.store.config.timezone_source = "manual";
        this.timezoneStatus =
          `Set to ${result.timezone} from your network. Save settings to apply it.`;
      } catch (error) {
        this.timezoneStatus =
          `Automatic time zone was unavailable: ${error.message} Choose one from the list.`;
      } finally {
        this.timezoneBusy = false;
      }
    },
  },
  template: `
    <div>
    <h2 class="fs-4 fw-semibold mb-3"><i class="bi bi-cpu me-2"></i>System</h2>

    <!-- ====== Display ====== -->
    <div id="group-display" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-pip me-2"></i>Display</p>

      <div class="mb-3">
        <h5>Colour Theme</h5>
        <select class="form-select form-select-sm" name="colour_theme" style="max-width:200px"
                v-model.number="store.config.colour_theme">
          <option :value="0">Default</option>
          <option :value="1">Monochrome</option>
          <option :value="2">Pastel</option>
          <option :value="3">Classic (v1)</option>
        </select>
      </div>

      <div class="mb-3">
        <h5>Animation Speed</h5>
        <select class="form-select form-select-sm" name="display_speed" style="max-width:220px"
                v-model="store.config.display_speed">
          <option value="slower">Slower</option>
          <option value="default">Default</option>
          <option value="faster">Faster</option>
        </select>
        <div class="form-text text-muted small">Adjust how quickly the display updates and animates.</div>
      </div>

      <div class="mb-3">
        <h5>Brightness</h5>
        <div v-show="!store.isAdvancedBrightness">
          <label class="form-label small">Level: {{ store.config.screen_brightness }}/5</label>
          <input type="range" class="form-range pt-3 px-2" name="screen_brightness" id="screen_brightness"
              min="1" max="5" step="1" v-model.number="store.config.screen_brightness"
              style="max-width:240px" />
          <div class="form-text text-muted small">
            Used outside any scheduled dimming or sleep window.
          </div>
        </div>
        <div v-show="store.isAdvancedBrightness" class="form-text text-muted small">
          Brightness is controlled by the fine-tune schedule on the
          <strong>Sleep</strong> tab.
        </div>
        <div v-if="store.ui.inSchedule" class="alert alert-warning small mt-2 mb-0 py-2">
          <i class="bi bi-exclamation-triangle me-1"></i>
          The brightness schedule is currently active - changes to the default brightness
          will not take effect until the scheduled period ends.
        </div>
      </div>
    </div>


    <!-- ====== Hardware ====== -->
    <div id="group-hardware" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-motherboard me-2"></i>Hardware</p>

      <div class="mb-3">
        <h5>LED Matrix Bonnet</h5>
        <div class="btn-group w-100" role="group" aria-label="LED matrix bonnet type">
          <input type="radio" class="btn-check" name="bonnet_type" id="bonnet_type_single"
                 value="single" autocomplete="off"
                 :checked="store.config.bonnet_type !== 'triple'"
                 @change="store.config.bonnet_type = 'single'" />
          <label class="btn btn-outline-primary btn-sm" for="bonnet_type_single">Single Bonnet</label>

          <input type="radio" class="btn-check" name="bonnet_type" id="bonnet_type_triple"
                 value="triple" autocomplete="off"
                 :checked="store.config.bonnet_type === 'triple'"
                 @change="store.config.bonnet_type = 'triple'" />
          <label class="btn btn-outline-primary btn-sm" for="bonnet_type_triple">Triple Bonnet</label>
        </div>
        <div class="form-text text-muted small">
          Choose <strong>Single Bonnet</strong> for the standard Adafruit RGB Matrix Bonnet/HAT.
          Choose <strong>Triple Bonnet</strong> for the Adafruit Triple LED Matrix Bonnet, with all
          three panels daisy-chained from port 1. These options only apply to older Pi models using
          the rgbmatrix library.
        </div>
      </div>

      <hr class="my-3" />

      <div v-show="store.config.bonnet_type !== 'triple'">
        <div class="mb-3">
          <h5>Adafruit HAT Mode</h5>
          <div class="btn-group w-100" role="group" aria-label="Adafruit HAT mode">
            <input type="radio" class="btn-check" name="hat_pwm_enabled" id="hat_pwm_quality"
                   value="quality" autocomplete="off"
                   :checked="store.config.hat_pwm_enabled"
                   @change="store.config.hat_pwm_enabled = true" />
            <label class="btn btn-outline-primary btn-sm" for="hat_pwm_quality">Quality Mode (Adafruit PWM Enabled)</label>

            <input type="radio" class="btn-check" name="hat_pwm_enabled" id="hat_pwm_convenience"
                   value="convenience" autocomplete="off"
                   :checked="!store.config.hat_pwm_enabled"
                   @change="store.config.hat_pwm_enabled = false" />
            <label class="btn btn-outline-primary btn-sm" for="hat_pwm_convenience">Convenience Mode</label>
          </div>
          <div class="form-text text-muted small">
            If you soldered the bridge and selected Quality during setup, choose Quality Mode here to enable
            Adafruit PWM mode. Otherwise choose Convenience Mode. These options have no effect on a Pi 5; they
            only apply to older Pi models using the rgbmatrix library.
          </div>
        </div>

        <hr class="my-3" />
      </div>

      <div class="mb-3">
        <h5>Display Scan Rate</h5>
        <div class="btn-group w-100" role="group" aria-label="Display Scan Rate">
          <input type="radio" class="btn-check" name="display_scan_rate" id="display_scan_rate_16"
                 value="16" autocomplete="off"
                 :checked="store.config.display_scan_rate !== 32"
                 @change="store.config.display_scan_rate = 16" />
          <label class="btn btn-outline-primary btn-sm" for="display_scan_rate_16">1:16</label>

          <input type="radio" class="btn-check" name="display_scan_rate" id="display_scan_rate_32"
                 value="32" autocomplete="off"
                 :checked="store.config.display_scan_rate === 32"
                 @change="store.config.display_scan_rate = 32" />
          <label class="btn btn-outline-primary btn-sm" for="display_scan_rate_32">1:32</label>
        </div>
        <div class="form-text text-warning small"><i class="bi bi-exclamation-triangle me-1"></i>Experimental feature.</div>
        <div class="form-text text-muted small">
          LED panels are either 1:16 or 1:32 scan rate. 64x32 panels are usually 1:16, but if you can only see
          half the image you likely have a 1:32 panel (these are normally cut-down 64x64 panels). You can sometimes
          tell from the serial number on the back of the panel &mdash; look for <code>16S</code> or <code>32S</code>.
          You will need to solder a bridge at location <code>E</code>.
          <a href="https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi/matrix-setup#configure-for-64x64-matrix-3200944" target="_blank">
            There's more information here on the adafruit website.
          </a>
        </div>
      </div>

      <hr class="my-3" />

      <div class="mb-2 form-check">
        <input type="checkbox" class="form-check-input" name="screen_rotate" id="screen_rotate"
            v-model="store.config.screen_rotate" />
        <label class="form-check-label" for="screen_rotate">Rotate display 180°</label>
        <div class="form-text text-muted small">Useful if you want to flip the unit and route cables from the other side.</div>
      </div>

      <hr class="my-3" />

      <div class="mb-3">
        <h5>GPIO Slowdown</h5>
        <label class="form-label small">Value (1-4)</label>
        <input type="number" min="1" max="4" class="form-control form-control-sm"
               name="gpio_slowdown" v-model.number="store.config.gpio_slowdown" style="max-width:80px" />
        <div class="form-text text-muted small">Increase if you see flickering. Pi 4 usually needs 4.</div>
      </div>

      <hr class="my-3" />

      <div class="mb-3">
        <h5>Loading Indicator</h5>
        <select class="form-select form-select-sm" name="loading_indicator" id="loading_indicator"
                style="max-width:200px" v-model="store.config.loading_indicator">
          <option value="none">None</option>
          <option value="pixel">Pixel</option>
          <option value="gpio">GPIO LED</option>
        </select>
        <div class="form-text text-muted small">
          Choose how FlightTracker indicates it is searching for flights. &quot;Pixel&quot; blinks an on-screen
          pixel, &quot;GPIO LED&quot; blinks an external LED, &quot;None&quot; disables the indicator.
        </div>
      </div>

      <div v-show="store.config.loading_indicator === 'gpio'">
        <label class="form-label small mt-2">GPIO pin</label>
        <input type="number" min="1" max="40" class="form-control form-control-sm"
               name="loading_led_gpio_pin" v-model.number="store.config.loading_led_gpio_pin"
               style="max-width:80px" />
        <div class="form-text text-muted small">An external LED can be used to indicate the search for flights. Requires LED driving circuitry.</div>
      </div>

      <hr class="my-3" />

      <div class="mb-3">
        <h5>Panel Colour Order</h5>
        <select class="form-select form-select-sm" name="panel_colour_order" id="panel_colour_order"
                style="max-width:200px" v-model="store.config.panel_colour_order">
          <option value="RGB">RGB (default)</option>
          <option value="RBG">RBG</option>
          <option value="BGR">BGR</option>
          <option value="BRG">BRG</option>
          <option value="GBR">GBR</option>
          <option value="GRB">GRB</option>
        </select>
        <div class="form-text text-muted small">
          The order the red, green and blue LEDs are wired on your panel. Set this if colours appear
          swapped on the display (e.g. red shows as blue). Most panels are RGB; if yours isn't, try the
          alternative orders until the colours look right.
        </div>
      </div>
    </div>

    <!-- ====== Web-Interface ====== -->
    <div id="group-web-interface" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-filetype-html me-2"></i>Web Interface</p>

      <div class="mb-2 form-check">
        <input type="checkbox" class="form-check-input" name="web_interface_enabled"
               id="web_interface_enabled" v-model="store.config.web_interface_enabled" />
        <label class="form-check-label" for="web_interface_enabled">Enable web interface on next boot</label>
        <div class="form-text text-muted small">
          If disabled, the config UI will not start and no QR code will be shown.
          Re-enable by editing <code>config.json</code> directly.
        </div>
      </div>

      <div class="mb-3">
        <label class="form-label small">Web interface port (1024-65535)</label>
        <input type="number" min="1024" max="65535" class="form-control form-control-sm"
               name="web_port" v-model.number="store.config.web_port" style="max-width:120px" />
        <div class="form-text text-muted small">TCP port for this interface. Change requires a restart.</div>
      </div>
    </div>

    <!-- ====== Defaults ====== -->
    <div id="group-defaults" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-rulers me-2"></i>Defaults</p>

      <h5>Screen Units</h5>

      <div class="mb-3">
        <label class="form-label small">Flight scenes</label>
        <select class="form-select form-select-sm" name="flight_units" style="max-width:220px"
                v-model="store.config.flight_units">
          <option value="metric">Metric (m, km/h, m/s)</option>
          <option value="standard">Standard (ft, mph, ft/min)</option>
        </select>
        <div class="form-text text-muted small">Applies to the flight data panel, custom flight details, and satellite altitude/speed.</div>
      </div>

      <div class="mb-3">
        <label class="form-label small">Idle screens</label>
        <select class="form-select form-select-sm" name="idle_units" style="max-width:220px"
                v-model="store.config.idle_units">
          <option value="metric">Metric (°C, mm, km/h)</option>
          <option value="standard">Standard (°F, in, mph)</option>
        </select>
        <div class="form-text text-muted small">Applies to idle-screen weather and forecast values. Standard units are the default.</div>
      </div>

      <div class="mb-3">
        <label class="form-label small">Number separator</label>
        <select class="form-select form-select-sm" name="number_separator" style="max-width:180px"
                v-model="store.config.number_separator">
          <option value="none">None (10000)</option>
          <option value="comma">Comma (10,000)</option>
          <option value="period">Period (10.000)</option>
        </select>
        <div class="form-text text-muted small">How large numbers are grouped in the plane details scroller.</div>
      </div>

      <hr />

      <h5>Clock and Date</h5>

      <div class="mb-2 form-check">
        <input type="checkbox" class="form-check-input" name="clock_24hr" id="clock_24hr"
               v-model="store.config.clock_24hr" />
        <label class="form-check-label" for="clock_24hr">24-hour clock</label>
      </div>

      <div class="mb-2">
        <label class="form-label small">Date format</label>
        <select class="form-select form-select-sm" name="date_format" style="max-width:200px"
                v-model.number="store.config.date_format">
          <option :value="0">Month Name Day Year (November 1st 2026)</option>
          <option :value="1">DD-MM-YYYY</option>
          <option :value="2">MM-DD-YYYY</option>
        </select>
      </div>

      <div class="mb-2">
        <label class="form-label small" for="timezone">Time zone</label>
        <div class="d-flex gap-2 align-items-start flex-wrap">
          <input type="text" class="form-control form-control-sm" id="timezone" name="timezone"
                 list="timezone-options" v-model="store.config.timezone"
                 :placeholder="store.ui.systemTimezone || 'System default'"
                 style="max-width:320px" />
          <button type="button" class="btn btn-outline-secondary btn-sm"
                  :disabled="timezoneBusy" @click="useIpTimezone">
            <span v-if="timezoneBusy" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-geo-alt me-1"></i>Use network location
          </button>
        </div>
        <datalist id="timezone-options">
          <option v-for="zone in store.ui.timezoneOptions" :key="zone" :value="zone"></option>
        </datalist>
        <div class="form-text text-muted small">
          Controls the clock, date, sunrise/sunset and the screen schedule. Leave blank to
          follow the Pi's system time zone<span v-if="store.ui.systemTimezone">
          (currently <strong>{{ store.ui.systemTimezone }}</strong>)</span>.
        </div>
        <div v-if="timezoneStatus" class="form-text small">{{ timezoneStatus }}</div>
      </div>
    </div>
    </div>
  `,
});