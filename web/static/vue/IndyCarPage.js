/**
 * INDYCAR page - live scene options, champion celebration, and previews.
 */

import { defineComponent } from "./vendor.js";

export default defineComponent({
  name: "IndyCarPage",
  props: {
    store: { type: Object, required: true },
  },
  template: `
    <div>
    <h2 class="fs-4 fw-semibold mb-3"><i class="bi bi-flag-checkered me-2"></i>INDYCAR</h2>

    <!-- ====== Live race display ====== -->
    <div id="group-indycar" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-flag me-2"></i>Live Race Display</p>

      <div class="form-check mb-3">
        <input type="checkbox" class="form-check-input" id="indycar_enabled"
               name="indycar_enabled" :value="true"
               v-model="store.config.indycar_enabled" />
        <label class="form-check-label" for="indycar_enabled">Enable INDYCAR live scenes</label>
        <div class="form-text text-muted small">
          Shows the Top 3 and tracked-driver scenes while an INDYCAR session is live. Off by default.
        </div>
      </div>

      <div class="mb-3">
        <label class="form-label small" for="indycar_tracked_driver">Tracked driver</label>
        <input type="text" class="form-control form-control-sm" id="indycar_tracked_driver"
               name="indycar_tracked_driver" maxlength="40" style="max-width:260px"
               placeholder="Car number or surname"
               v-model="store.config.indycar_tracked_driver" />
        <div class="form-text text-muted small">
          Enter a car number (for example <strong>11</strong>) or surname (for example
          <strong>Palou</strong>). Leave blank to show the Top 3 scene. During qualifying
          the scene shows qualifying time, gap, and speed instead of race gaps.
        </div>
      </div>
    </div>

    <!-- ====== Champion ====== -->
    <div id="group-indycar-champion" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-trophy me-2"></i>Drivers Champion</p>

      <div class="form-check mb-3">
        <input type="checkbox" class="form-check-input" id="indycar_champion_enabled"
               name="indycar_champion_enabled" :value="true"
               v-model="store.config.indycar_champion_enabled" />
        <label class="form-check-label" for="indycar_champion_enabled">Celebrate the champion</label>
        <div class="form-text text-muted small">
          Flashes a Drivers Champion celebration once the points leader has clinched.
          It never interrupts a live session, and it stops after the duration below.
        </div>
      </div>

      <div class="mb-3">
        <label class="form-label small" for="indycar_champion_override">Manual champion override</label>
        <input type="text" class="form-control form-control-sm" id="indycar_champion_override"
               name="indycar_champion_override" maxlength="40" style="max-width:260px"
               placeholder="Driver name or car number"
               v-model="store.config.indycar_champion_override" />
        <div class="form-text text-muted small">
          Optional. Use this off-season, when the feeds carry no champion field, to force
          the celebration for a specific driver.
        </div>
      </div>

      <div class="mb-0">
        <label class="form-label small" for="indycar_champion_flash_seconds">Celebration duration (seconds)</label>
        <input type="number" class="form-control form-control-sm" id="indycar_champion_flash_seconds"
               name="indycar_champion_flash_seconds" min="10" max="600" step="10"
               style="max-width:140px"
               v-model.number="store.config.indycar_champion_flash_seconds" />
        <div class="form-text text-muted small">
          How long the flashing celebration may occupy the screen. Defaults to 60 seconds.
        </div>
      </div>
    </div>

    <!-- ====== Preview ====== -->
    <div id="group-indycar-testing" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-play-circle me-2"></i>Preview</p>

      <div class="form-check mb-3">
        <input type="checkbox" class="form-check-input" id="indycar_test_mode"
               name="indycar_test_mode" :value="true"
               v-model="store.config.indycar_test_mode" />
        <label class="form-check-label" for="indycar_test_mode">Use bundled demo data</label>
        <div class="form-text text-muted small">
          Replaces the live feeds with recorded snapshots, so the INDYCAR scenes can be
          demonstrated without a race weekend. The debug selector under
          <strong>Sky Monitoring &rarr; Debug</strong> also previews with these snapshots
          automatically.
        </div>
      </div>

      <div class="form-check mb-0">
        <input type="checkbox" class="form-check-input" id="indycar_test_qualifying"
               name="indycar_test_qualifying" :value="true"
               v-model="store.config.indycar_test_qualifying" />
        <label class="form-check-label" for="indycar_test_qualifying">Show the qualifying layout</label>
        <div class="form-text text-muted small">
          Used by the tracked-driver preview to swap race gaps for qualifying time,
          gap to provisional pole, and speed.
        </div>
      </div>
    </div>
    </div>
  `,
});
