/**
 * Wi-Fi page - current network, changing networks, and the setup hotspot.
 *
 * The settings form is one big POST, so these controls deliberately use
 * buttons and fetch() instead of named inputs.  That keeps Wi-Fi changes
 * out of "Save & Restart" and lets the page report the result immediately.
 */

import { defineComponent } from "./vendor.js";

export default defineComponent({
  name: "WifiPage",
  props: {
    store: { type: Object, required: true },
  },
  data() {
    return {
      status: null,
      statusLoading: true,
      statusError: "",
      ssid: "",
      password: "",
      connectBusy: false,
      connectMessage: "",
      connectError: "",
      setupBusy: false,
      setupMessage: "",
      setupError: "",
    };
  },
  computed: {
    connectedLabel() {
      if (!this.status) return "Checking…";
      if (this.status.setup_active) return "Setup hotspot";
      if (this.status.connected) return this.status.ssid || "Connected";
      if (this.status.wired) return "Ethernet";
      return "Not connected";
    },
    connectedClass() {
      if (!this.status) return "text-bg-secondary";
      if (this.status.setup_active) return "text-bg-warning";
      if (this.status.connected || this.status.wired) return "text-bg-success";
      return "text-bg-danger";
    },
  },
  mounted() {
    this.loadStatus();
  },
  methods: {
    async loadStatus() {
      this.statusLoading = true;
      this.statusError = "";
      try {
        const response = await fetch(
          this.store.ui.urls.wifiStatus || "/api/wifi/status",
          {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
          },
        );
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not read the Wi-Fi status.");
        }
        this.status = result;
      } catch (error) {
        this.statusError = error.message;
      } finally {
        this.statusLoading = false;
      }
    },
    async connect() {
      if (!this.ssid.trim()) {
        this.connectError = "Enter the Wi-Fi network name.";
        return;
      }
      if (this.password.length < 8) {
        this.connectError = "The Wi-Fi password must be at least 8 characters.";
        return;
      }

      this.connectBusy = true;
      this.connectMessage = "";
      this.connectError = "";
      try {
        const response = await fetch(
          this.store.ui.urls.wifiConnect || "/api/wifi/connect",
          {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
              Accept: "application/json",
            },
            body: new URLSearchParams({
              csrf_token: this.store.ui.csrfToken,
              ssid: this.ssid.trim(),
              password: this.password,
            }),
          },
        );
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not change the Wi-Fi network.");
        }
        this.connectMessage = result.message;
        this.ssid = "";
        this.password = "";
      } catch (error) {
        this.connectError = error.message;
      } finally {
        this.connectBusy = false;
      }
    },
    async runSetupAction(path, confirmation) {
      if (!window.confirm(confirmation)) return;
      this.setupBusy = true;
      this.setupMessage = "";
      this.setupError = "";
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
        this.setupMessage = result.message;
      } catch (error) {
        this.setupError =
          "The setup hotspot may have started and disconnected this page. " +
          "Scan the Wi-Fi QR code on the display to reconnect.";
      } finally {
        this.setupBusy = false;
      }
    },
    openSetupHotspot() {
      this.runSetupAction(
        this.store.ui.urls.wifiSetupReset || "/wifi-setup/reset",
        "Open the setup hotspot? The Pi may briefly disconnect from your home Wi-Fi.",
      );
    },
    forgetWifi() {
      this.runSetupAction(
        this.store.ui.urls.wifiSetupForget || "/wifi-setup/forget",
        "Delete all saved Wi-Fi networks and open the setup hotspot? The Pi will disconnect from this network. Scan the QR code on the display to set up Wi-Fi again.",
      );
    },
  },
  template: `
    <div>
    <h2 class="fs-4 fw-semibold mb-3"><i class="bi bi-wifi me-2"></i>Wi-Fi</h2>

    <!-- ====== Current network ====== -->
    <div id="group-wifi" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-wifi me-2"></i>Network connection</p>

      <div v-if="statusLoading" class="text-muted small mb-3">
        <span class="spinner-border spinner-border-sm me-2" role="status"></span>
        Checking the current connection…
      </div>
      <div v-else-if="statusError" class="alert alert-warning py-2 mb-3">
        <i class="bi bi-exclamation-triangle me-1"></i>{{ statusError }}
        <button type="button" class="btn btn-sm btn-outline-secondary ms-2"
                @click="loadStatus">Retry</button>
      </div>
      <div v-else class="mb-3">
        <div class="d-flex align-items-center flex-wrap gap-2 mb-2">
          <span class="badge" :class="connectedClass">{{ connectedLabel }}</span>
          <span v-if="status && status.ip" class="text-muted small">
            IP address <code>{{ status.ip }}</code>
          </span>
          <span v-if="status && status.wired && !status.setup_active"
                class="text-muted small">Ethernet is also connected.</span>
        </div>
        <button type="button" class="btn btn-sm btn-outline-secondary"
                :disabled="statusLoading" @click="loadStatus">
          <i class="bi bi-arrow-clockwise me-1"></i>Refresh status
        </button>
      </div>

      <div v-if="status && status.setup_active" class="alert alert-warning small py-2">
        <i class="bi bi-broadcast me-1"></i>
        The setup hotspot is open. Enter the Wi-Fi network the Pi should use
        below. The hotspot turns off after the Pi connects.
      </div>

      <h5 class="mt-3">Change network</h5>
      <p class="text-muted small mb-2">
        The Pi disconnects from its current network while it joins the new one.
        If you are using the setup hotspot, rejoin your home Wi-Fi after saving.
      </p>

      <div v-if="connectMessage" class="alert alert-success py-2 small">
        {{ connectMessage }}
      </div>
      <div v-if="connectError" class="alert alert-danger py-2 small">
        {{ connectError }}
      </div>

      <div class="row g-2">
        <div class="col-md-6">
          <label class="form-label small" for="wifi-ssid">Wi-Fi network name</label>
          <input type="text" class="form-control" id="wifi-ssid"
                 v-model="ssid" maxlength="32" autocomplete="off"
                 @keydown.enter.prevent />
        </div>
        <div class="col-md-6">
          <label class="form-label small" for="wifi-password">Wi-Fi password</label>
          <input type="password" class="form-control" id="wifi-password"
                 v-model="password" autocomplete="new-password"
                 @keydown.enter.prevent />
        </div>
      </div>
      <p class="form-text text-muted small">
        Passwords are 8–63 characters. Leave these boxes blank to keep the
        current network.
      </p>
      <button type="button" class="btn btn-primary btn-sm"
              :disabled="connectBusy" @click="connect">
        <span v-if="connectBusy" class="spinner-border spinner-border-sm me-2" role="status"></span>
        <i v-else class="bi bi-wifi me-1"></i>
        {{ connectBusy ? 'Connecting…' : 'Connect' }}
      </button>
    </div>

    <!-- ====== Setup hotspot ====== -->
    <div id="group-wifi-setup" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-router me-2"></i>Setup hotspot and recovery</p>

      <div v-if="setupMessage" class="alert alert-success py-2 small">{{ setupMessage }}</div>
      <div v-if="setupError" class="alert alert-warning py-2 small">{{ setupError }}</div>

      <div class="d-flex align-items-center justify-content-between flex-wrap gap-3 border-bottom pb-3 mb-3">
        <div>
          <div class="fw-semibold">Open the setup hotspot</div>
          <div class="text-muted small">
            Starts the protected hotspot and QR code without deleting your saved
            Wi-Fi. Use it when the Pi is on a network you cannot reach.
          </div>
        </div>
        <button type="button" class="btn btn-outline-primary btn-sm"
                :disabled="setupBusy" @click="openSetupHotspot">
          <i class="bi bi-broadcast me-1"></i>Open Hotspot
        </button>
      </div>

      <div class="d-flex align-items-center justify-content-between flex-wrap gap-3">
        <div>
          <div class="fw-semibold">Forget Wi-Fi networks</div>
          <div class="text-muted small">
            Deletes every saved Wi-Fi network and opens the first-boot hotspot,
            exactly like a fresh install. The web password and settings are kept.
          </div>
        </div>
        <button type="button" class="btn btn-outline-danger btn-sm"
                :disabled="setupBusy" @click="forgetWifi">
          <i class="bi bi-wifi-off me-1"></i>Forget Wi-Fi
        </button>
      </div>
    </div>
    </div>
  `,
});
