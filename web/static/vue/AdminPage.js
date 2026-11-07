/**
 * Admin page - logging, password, cache, backup, help, version.
 */

import { defineComponent } from "./vendor.js";

export default defineComponent({
  name: "AdminPage",
  props: {
    store: { type: Object, required: true },
  },
  data() {
    return {
      newPassword: "",
      confirmPassword: "",
      maintenanceBusy: false,
      maintenanceMessage: "",
      maintenanceError: "",
      sshState: { available: true, enabled: false, active: false },
      sshLoading: true,
      sshBusy: false,
      sshMessage: "",
      sshError: "",
    };
  },
  mounted() {
    this.loadSshState();
  },
  methods: {
    async loadSshState() {
      this.sshError = "";
      try {
        const response = await fetch(
          this.store.ui.urls.sshAccess || "/remote-access/ssh",
          {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
          },
        );
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not read the SSH state.");
        }
        this.sshState = result;
      } catch (error) {
        this.sshError = error.message;
      } finally {
        this.sshLoading = false;
      }
    },
    async toggleSsh() {
      const enable = !this.sshState.enabled;
      const confirmation = enable
        ? "Enable SSH? Anyone on this local network can try to log in with the Pi username and password. The web UI does not need SSH."
        : "Disable SSH? Remote terminal access will stop until you enable it again.";
      if (!window.confirm(confirmation)) return;

      this.sshBusy = true;
      this.sshMessage = "";
      this.sshError = "";
      try {
        const response = await fetch(
          this.store.ui.urls.sshAccess || "/remote-access/ssh",
          {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
              Accept: "application/json",
            },
            body: new URLSearchParams({
              csrf_token: this.store.ui.csrfToken,
              action: enable ? "on" : "off",
            }),
          },
        );
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not change the SSH state.");
        }
        this.sshMessage = result.message;
        this.sshState =
          result.state || { ...this.sshState, enabled: enable, active: enable };
      } catch (error) {
        this.sshError = error.message;
        await this.loadSshState();
      } finally {
        this.sshBusy = false;
      }
    },
    async runMaintenanceAction(path, confirmation, networkMaySwitch = false) {
      if (!window.confirm(confirmation)) return;
      this.maintenanceBusy = true;
      this.maintenanceMessage = "";
      this.maintenanceError = "";
      try {
        const response = await fetch(path, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            Accept: "application/json",
          },
          body: new URLSearchParams({
            csrf_token: this.store.ui.csrfToken,
          }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "The action failed.");
        this.maintenanceMessage = result.message;
        window.setTimeout(() => window.location.reload(), 2500);
      } catch (error) {
        this.maintenanceError = networkMaySwitch
          ? "The hotspot may have started and disconnected this page. Scan the Wi-Fi QR code on the display; your saved home Wi-Fi details are kept."
          : error.message;
      } finally {
        this.maintenanceBusy = false;
      }
    },
  },
  template: `
    <div>
    <h2 class="fs-4 fw-semibold mb-3"><i class="bi bi-shield-lock me-2"></i>Admin</h2>

    <!-- ====== Logging ====== -->
    <div id="group-logging" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-terminal me-2"></i>Logging</p>
      <div class="mb-3">
        <h5>Log Level</h5>
        <select class="form-select form-select-sm" name="log_level" style="max-width:200px"
                v-model="store.config.log_level">
          <option value="DEBUG">Debug (verbose)</option>
          <option value="INFO">Info (default)</option>
          <option value="WARNING">Warning</option>
          <option value="ERROR">Error</option>
          <option value="CRITICAL">Critical</option>
        </select>
        <div class="form-text text-muted small">
          Controls how much detail is captured for the
          <a :href="store.ui.urls.logs">log viewer</a>. Change requires a restart.
        </div>
      </div>
      <div class="form-check">
        <input type="checkbox" class="form-check-input" id="provider_usage_logging"
               name="provider_usage_logging" :value="true"
               v-model="store.config.provider_usage_logging" />
        <label class="form-check-label small" for="provider_usage_logging">
          Record provider API usage
        </label>
        <div class="form-text text-muted small">
          Counts how often each lookup provider is used and how often they come back empty.
          View the totals on the
          <a :href="store.ui.urls.statusApi">API Usage</a> page. Turning this off stops new
          tallies; recorded history is kept until cleared there.
        </div>
      </div>
    </div>

    <!-- ====== Cache ====== -->
    <div id="group-clear-cache" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-database me-2"></i>Cache</p>
      <div class="row g-3 mb-2">
        <div class="col-12 col-md-6">
          <label class="form-label small mb-1" for="cache_aircraft_days">
            Aircraft cache duration (days)
          </label>
          <input type="number" class="form-control form-control-sm" id="cache_aircraft_days"
                 name="cache_aircraft_days" min="1" max="30" step="1"
                 v-model.number="store.config.cache_aircraft_days" style="width:8rem" />
          <div class="form-text text-muted small">
            How long aircraft details are reused from cache (1-30 days) before
            providers are asked again.
          </div>
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label small mb-1" for="cache_route_hours">
            Route cache duration (hours)
          </label>
          <input type="number" class="form-control form-control-sm" id="cache_route_hours"
                 name="cache_route_hours" min="1" max="48" step="1"
                 v-model.number="store.config.cache_route_hours" style="width:8rem" />
          <div class="form-text text-muted small">
            How long callsign routing is reused from cache (1-48 hours) before
            providers are asked again. Short is safer - flight numbers move between
            routes - but costs more lookups.
          </div>
        </div>
      </div>
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 border-top pt-3">
        <div>
          <div class="text-muted small">Clears cached lookup data and the TLE cache.</div>
          <div class="fw-semibold">Clearing cache will restart FlightTracker.</div>
        </div>
        <a :href="store.ui.urls.cacheClear" class="btn btn-outline-danger btn-sm">
          <i class="bi bi-trash3 me-1"></i>Clear Cache
        </a>
      </div>
    </div>

    <!-- ====== Backup ====== -->
    <div id="group-backup" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-file-earmark-arrow-down me-2"></i>Backup</p>
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
        <div>
          <div class="text-muted small">
            Download a full copy of your settings (including API keys) or restore from a previous export.
          </div>
          <div class="fw-semibold">Restoring will overwrite all settings and restart.</div>
        </div>
        <div class="d-flex gap-2 flex-wrap">
          <a :href="store.ui.urls.backupExport" class="btn btn-outline-primary btn-sm">
            <i class="bi bi-download me-1"></i>Export
          </a>
          <a :href="store.ui.urls.backupRestore" class="btn btn-outline-warning btn-sm">
            <i class="bi bi-upload me-1"></i>Restore
          </a>
        </div>
      </div>
    </div>

    <!-- ====== Recovery ====== -->
    <div id="group-recovery" class="card mb-3 p-3 border-danger">
      <p class="section-heading text-danger"><i class="bi bi-arrow-counterclockwise me-2"></i>Recovery</p>
      <div v-if="maintenanceMessage" class="alert alert-success py-2">{{ maintenanceMessage }}</div>
      <div v-if="maintenanceError" class="alert alert-warning py-2">{{ maintenanceError }}</div>
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-3 border-bottom pb-3 mb-3">
        <div>
          <div class="fw-semibold">Reset FlightTracker settings</div>
          <div class="text-muted small">
            Restore application settings to defaults. Your Wi-Fi details and web password are kept.
            FlightTracker will restart.
          </div>
        </div>
        <button type="button" class="btn btn-outline-danger btn-sm"
                :disabled="maintenanceBusy"
                @click="runMaintenanceAction('/settings/reset',
                  'Reset all FlightTracker settings to defaults? Your saved Wi-Fi and web password will be kept.')">
          Reset Settings
        </button>
      </div>
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-3">
        <div>
          <div class="fw-semibold">Change Wi-Fi network</div>
          <div class="text-muted small">
            Open the protected setup hotspot and QR code. Existing Wi-Fi details are kept until
            you successfully save new ones.
          </div>
        </div>
        <button type="button" class="btn btn-outline-danger btn-sm"
                :disabled="maintenanceBusy"
                @click="runMaintenanceAction('/wifi-setup/reset',
                  'Open the setup hotspot? The Pi may briefly disconnect from your home Wi-Fi.',
                  true)">
          <i class="bi bi-wifi me-1"></i>Reset Wi-Fi
        </button>
      </div>
    </div>

    <!-- ====== Remote Access ====== -->
    <div id="group-remote-access" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-router me-2"></i>Remote Access</p>
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-3">
        <div>
          <div class="fw-semibold">SSH server</div>
          <div class="text-muted small">
            SSH opens a terminal on the Pi from another device on the same network.
            Hobby Ticker's web pages do not need it. Leave it off unless you are
            troubleshooting.
          </div>
          <div class="small mt-2" v-if="sshLoading">
            <span class="text-muted">Checking SSH state…</span>
          </div>
          <div class="small mt-2" v-else-if="!sshState.available">
            <span class="text-warning">SSH control is not installed on this system.</span>
          </div>
          <div class="small mt-2" v-else>
            <span v-if="sshState.enabled" class="text-success">
              <i class="bi bi-check-circle me-1"></i>On
            </span>
            <span v-else class="text-secondary">
              <i class="bi bi-x-circle me-1"></i>Off
            </span>
            <span v-if="sshState.enabled && !sshState.active" class="text-warning ms-2">
              Enabled, but not running. Toggle it off and on again.
            </span>
          </div>
        </div>
        <button type="button"
                class="btn btn-sm"
                :class="sshState.enabled ? 'btn-outline-danger' : 'btn-outline-primary'"
                :disabled="sshBusy || sshLoading || !sshState.available"
                @click="toggleSsh">
          <span v-if="sshBusy" class="spinner-border spinner-border-sm me-1" role="status"></span>
          <i v-else class="bi bi-terminal me-1"></i>
          {{ sshState.enabled ? 'Disable SSH' : 'Enable SSH' }}
        </button>
      </div>
      <div class="alert alert-warning py-2 mt-3 mb-0 small">
        <i class="bi bi-exclamation-triangle me-1"></i>
        SSH is only reachable from devices on the same local network. It is not exposed
        to the internet. Guests on this network may still attempt a login, so keep the
        Pi password strong.
      </div>
      <div v-if="sshMessage" class="alert alert-success py-2 mt-3 mb-0">{{ sshMessage }}</div>
      <div v-if="sshError" class="alert alert-warning py-2 mt-3 mb-0">{{ sshError }}</div>
    </div>

    <!-- ====== Change Password ====== -->
    <div id="group-password" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-key me-2"></i>Change Password</p>
      <div class="row g-3">
        <div class="col-sm-6">
          <label class="form-label small">New password</label>
          <input type="password" class="form-control form-control-sm"
                 name="new_password" id="new_password" autocomplete="new-password"
                 v-model="newPassword" placeholder="Leave blank to keep current" />
        </div>
        <div class="col-sm-6">
          <label class="form-label small">Confirm new password</label>
          <input type="password" class="form-control form-control-sm"
                 name="confirm_password" id="confirm_password" autocomplete="new-password"
                 v-model="confirmPassword" placeholder="Repeat new password" />
        </div>
      </div>
    </div>

    <!-- ====== Version ====== -->
    <div id="group-version" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-info-circle me-2"></i>Version</p>
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
        <div>
          <div class="text-muted small">Current version</div>
          <div class="fs-5 fw-semibold">{{ store.ui.currentVersion }}</div>
          <a :href="store.ui.urls.update" class="btn btn-outline-warning btn-sm mt-2">
            <i class="bi bi-arrow-repeat me-1"></i>Check for Updates
          </a>
        </div>
      </div>
    </div>

    <!-- ====== Help & Support ====== -->
    <div id="group-help" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-question-circle me-2"></i>Help &amp; Support</p>
      <div class="text-muted small mb-2">
        <p>
          Found a bug or need a hand? Open an issue on
          <a href="https://github.com/ColinWaddell/FlightTracker/issues" target="_blank">GitHub</a>.
        </p>
        <p>
          If you need to post your config data use the button below, it removes your password and
          API keys making it safe to post online.
        </p>
      </div>
      <a :href="store.ui.urls.debugConfig" class="btn btn-sm btn-outline-secondary">
        <i class="bi bi-download me-1"></i>Download debug config
      </a>
    </div>
    </div>
  `,
});