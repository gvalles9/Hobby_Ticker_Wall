/**
 * Root Vue application for the settings page.
 *
 * Holds the reactive store, manages routing (page visibility), handles
 * sidebar navigation (scroll-to-section), and form submission.
 */

import { defineComponent, ref, onMounted, nextTick } from "./vendor.js";
import { createStore } from "./store.js";
import SettingsSidebar from "./SettingsSidebar.js";
import SkyMonitoringPage from "./SkyMonitoringPage.js";
import DataSourcePage from "./DataSourcePage.js";
import DefaultScreenPage from "./DefaultScreenPage.js";
import HardwarePage from "./HardwarePage.js";
import AdminPage from "./AdminPage.js";
import IndyCarPage from "./IndyCarPage.js";

const PAGES = [
  { name: "sky-monitoring", component: SkyMonitoringPage },
  { name: "data-source", component: DataSourcePage },
  { name: "default-screen", component: DefaultScreenPage },
  { name: "indycar", component: IndyCarPage },
  { name: "hardware", component: HardwarePage },
  { name: "admin", component: AdminPage },
];

export default defineComponent({
  name: "SettingsApp",
  components: { SettingsSidebar, SkyMonitoringPage, DataSourcePage, DefaultScreenPage, IndyCarPage, HardwarePage, AdminPage },
  setup() {
    const config = window.FT_CONFIG || {};
    const pageData = window.FT_PAGE_DATA || {};

    const store = createStore(config, pageData);

    const currentPage = ref("sky-monitoring");

    function showPage(pageName) {
      currentPage.value = pageName;
    }

    function scrollToSection(section) {
      nextTick(() => {
        const target = document.getElementById(section);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    function navigate({ route, section }) {
      const pageName = route.replace(/^\//, "");
      const currentPath = currentPage.value;

      if (currentPath === pageName) {
        scrollToSection(section);
      } else {
        showPage(pageName);
        setTimeout(() => scrollToSection(section), 80);
      }
    }

    // -- Form submission --------------------------------------------------
    function onSubmit() {
      store.ui.saving = true;
    }

    function applyDetectedLocation(latitude, longitude, source) {
      if (!["auto", "ip"].includes(store.config.location_source)) return;
      const latitudeOffset = 10 / 111;
      const longitudeOffset =
        10 /
        (111 *
          Math.max(Math.abs(Math.cos((latitude * Math.PI) / 180)), 0.01));
      const wrapLongitude = (value) => ((value + 180) % 360 + 360) % 360 - 180;
      store.config.flight_lat = latitude;
      store.config.flight_lng = longitude;
      store.config.flight_observer_lat = latitude;
      store.config.flight_observer_lng = longitude;
      store.config.flight_zone_tl_y = Math.min(90, latitude + latitudeOffset);
      store.config.flight_zone_tl_x = wrapLongitude(longitude - longitudeOffset);
      store.config.flight_zone_br_y = Math.max(-90, latitude - latitudeOffset);
      store.config.flight_zone_br_x = wrapLongitude(longitude + longitudeOffset);
      store.config.location_source = source;
      store.ui.locationStatus =
        `Location detected (${source === "browser" ? "device" : "IP estimate"}). Save settings to apply it.`;
    }

    async function useIpLocation() {
      try {
        const response = await fetch(pageData.urls?.ipLocation || "/api/location/ip", {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Location lookup failed.");
        const { latitude, longitude } = result;
        if (
          !Number.isFinite(latitude) ||
          !Number.isFinite(longitude) ||
          latitude < -90 ||
          latitude > 90 ||
          longitude < -180 ||
          longitude > 180
        ) {
          throw new Error("Location service returned invalid coordinates.");
        }
        applyDetectedLocation(latitude, longitude, "ip");
      } catch (error) {
        store.ui.locationStatus =
          `Automatic location was unavailable: ${error.message} Enter coordinates manually.`;
      }
    }

    function detectInitialLocation() {
      if (!pageData.locationDetectionEnabled) return;
      store.ui.locationStatus = "Finding your location…";
      if (!navigator.geolocation) {
        useIpLocation();
        return;
      }
      try {
        navigator.geolocation.getCurrentPosition(
          ({ coords }) => applyDetectedLocation(coords.latitude, coords.longitude, "browser"),
          useIpLocation,
          { enableHighAccuracy: false, maximumAge: 600000, timeout: 7000 },
        );
      } catch {
        useIpLocation();
      }
    }

    // -- Restore hash from URL on load --
    onMounted(() => {
      const hash = window.location.hash.replace(/^#\/?/, "");
      if (hash && PAGES.some((p) => p.name === hash)) {
        showPage(hash);
      }
      detectInitialLocation();
    });

    return {
      store,
      currentPage,
      pages: PAGES,
      navigate,
      onSubmit,
      scrollToSection,
    };
  },
  template: `
    <div class="container-fluid py-4" style="max-width:1100px">
      <div class="row">
        <!-- Sidebar -->
        <div class="col-md-3 mb-4">
          <settings-sidebar @navigate="navigate" />
        </div>

        <!-- Main content -->
        <div class="col-md-9">
          <form method="post" action="/settings" id="settings-form" novalidate @submit="onSubmit">
            <input type="hidden" name="csrf_token" :value="store.ui.csrfToken" />

            <!-- Template errors alert -->
            <div v-if="store.ui.templateErrors.length" class="alert alert-danger mb-3">
              <strong><i class="bi bi-exclamation-triangle me-1"></i>Template errors:</strong>
              Please fix the following issues in the
              <a href="javascript:void(0)"
                 @click="scrollToSection('group-plane-info')"
                 class="alert-link fw-bold">Plane Details</a>
              section:
              <ul class="mb-0 mt-1">
                <li v-for="err in store.ui.templateErrors" :key="err">{{ err }}</li>
              </ul>
            </div>

            <!-- Import failed alert -->
            <div v-if="store.ui.importFailed" class="alert alert-warning alert-dismissible fade show mb-3" role="alert">
              <strong><i class="bi bi-exclamation-triangle me-1"></i>Import failed:</strong>
              The last config import failed and your previous settings have been restored.
              <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>

            <!-- Server error alert -->
            <div v-if="store.ui.serverError" class="alert alert-danger mb-3">
              <strong>Error saving settings:</strong> {{ store.ui.serverError }}
            </div>

            <!-- Page content: every page stays mounted so all of its inputs
                 remain part of the form payload on save; v-show (not v-if)
                 toggles visibility only -->
            <component
              v-for="page in pages"
              :is="page.component"
              v-show="currentPage === page.name"
              :key="page.name"
              :store="store"
            />

            <!-- Save button -->
            <div class="d-grid mb-3">
              <button type="submit" id="save-btn" class="btn btn-primary btn-lg" :disabled="store.ui.saving">
                <span v-if="store.ui.saving" class="spinner-border spinner-border-sm me-2" role="status"></span>
                {{ store.ui.saving ? 'Saving…' : 'Save & Restart' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
});