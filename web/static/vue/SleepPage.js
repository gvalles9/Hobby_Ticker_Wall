/**
 * Sleep page - night standby and the brightness schedule.
 *
 * Standby is the brightness schedule held at level 0: the panels go dark,
 * the display stops polling, and the weather/satellite threads pause until
 * the window ends.  Keeping it on its own page makes the feature easy to
 * find instead of hiding it inside the display settings.
 */

import { defineComponent } from "./vendor.js";

export default defineComponent({
  name: "SleepPage",
  props: {
    store: { type: Object, required: true },
  },
  computed: {
    scheduleWindowLabel() {
      const [start, end] = this.store.ui.scheduleWindow;
      if (!start || !end) return "";
      const fmt = (t) =>
        this.store.formatTime(
          `${String(t.hour).padStart(2, "0")}:${String(t.minute).padStart(2, "0")}`
        );
      return `${fmt(start)} - ${fmt(end)}`;
    },
    inStandby() {
      if (this.store.isAdvancedBrightness) {
        const active = this.store.ui.scheduleAdvancedActive;
        return !!active && Number(active.brightness) === 0;
      }
      return (
        !!this.store.ui.inSchedule &&
        Number(this.store.config.screen_schedule_brightness) === 0
      );
    },
    dimmingOnly() {
      if (this.store.isAdvancedBrightness) {
        const active = this.store.ui.scheduleAdvancedActive;
        return !!active && Number(active.brightness) > 0;
      }
      return (
        !!this.store.ui.inSchedule &&
        Number(this.store.config.screen_schedule_brightness) > 0
      );
    },
  },
  template: `
    <div>
    <h2 class="fs-4 fw-semibold mb-3"><i class="bi bi-moon-stars me-2"></i>Sleep</h2>

    <!-- ====== Night standby ====== -->
    <div id="group-sleep" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-moon-stars me-2"></i>Night standby</p>

      <div class="alert alert-info small py-2 mb-3">
        <i class="bi bi-info-circle me-1"></i>
        Set the panels to switch off overnight instead of running all night.
        While the unit is in standby it stops polling flight, weather and
        satellite data, so it is quiet and uses only a few watts. The web
        interface stays available.
      </div>

      <div class="mb-3">
        <h5>Brightness Mode</h5>
        <div class="btn-group w-100 mb-1" role="group" aria-label="Brightness mode">
          <input type="radio" class="btn-check" name="brightness_mode" id="brightness_mode_simple"
                 value="simple" autocomplete="off"
                 v-model="store.config.brightness_mode" />
          <label class="btn btn-outline-primary btn-sm" for="brightness_mode_simple">
            <i class="bi bi-brightness-high me-1"></i>Simple
          </label>

          <input type="radio" class="btn-check" name="brightness_mode" id="brightness_mode_advanced"
                 value="advanced" autocomplete="off"
                 v-model="store.config.brightness_mode" />
          <label class="btn btn-outline-primary btn-sm" for="brightness_mode_advanced">
            <i class="bi bi-sliders me-1"></i>Fine-tune
          </label>
        </div>
        <div class="form-text text-muted small">
          Simple uses one sleep window. Fine-tune holds several brightness
          steps through the day.
        </div>
      </div>

      <div v-show="!store.isAdvancedBrightness">
        <div class="mb-2 form-check">
          <input type="checkbox" class="form-check-input" name="screen_schedule_enabled"
              id="screen_schedule_enabled" v-model="store.config.screen_schedule_enabled" />
          <label class="form-check-label" for="screen_schedule_enabled">Sleep on a schedule</label>
          <div class="form-text text-muted small">Switches the panels off at the sleep time and back on when the unit wakes.</div>
        </div>

        <div v-show="store.config.screen_schedule_enabled">
          <div class="form-check mb-2">
            <input type="checkbox" class="form-check-input" name="screen_schedule_auto" id="screen_schedule_auto"
                v-model="store.config.screen_schedule_auto" />
            <label class="form-check-label" for="screen_schedule_auto">Follow sunrise &amp; sunset</label>
            <div class="form-text text-muted small">Uses your flight location coordinates to estimate sunrise and sunset times instead of fixed hours.</div>
          </div>

          <div v-show="!store.config.screen_schedule_auto">
            <div class="row g-2 mt-1">
              <div class="col-auto">
                <label class="form-label small" for="screen_schedule_start">Sleep at</label>
                <input type="time" class="form-control form-control-sm"
                    id="screen_schedule_start"
                    name="screen_schedule_start" v-model="store.config.screen_schedule_start" />
              </div>
              <div class="col-auto">
                <label class="form-label small" for="screen_schedule_end">Wake at</label>
                <input type="time" class="form-control form-control-sm"
                    id="screen_schedule_end"
                    name="screen_schedule_end" v-model="store.config.screen_schedule_end" />
              </div>
            </div>
            <div class="form-text text-muted small">
              Windows that cross midnight are fine, for example
              <code>22:00</code> to <code>08:00</code>.
            </div>
          </div>

          <div class="row g-2 mt-2">
            <div class="col-auto">
              <label class="form-label small" for="screen_schedule_brightness">
                Night brightness: {{ store.config.screen_schedule_brightness }}/5 (0=off)
              </label>
              <input type="range" class="form-range pt-3 px-2" name="screen_schedule_brightness"
                  id="screen_schedule_brightness"
                  min="0" max="5" step="1" v-model.number="store.config.screen_schedule_brightness"
                  style="max-width:240px" />
              <div class="form-text text-muted small">
                Set to <code>0</code> for full standby (panels off, polling
                paused). Levels <code>1</code>-<code>5</code> only dim the
                display and keep polling.
              </div>
            </div>
          </div>

          <div v-if="inStandby" class="alert alert-secondary small py-2 mb-0">
            <i class="bi bi-moon-stars me-1"></i>
            Standing by now. The panels are off and background polling is
            paused until the schedule ends<span v-if="scheduleWindowLabel">
            ({{ scheduleWindowLabel }})</span>.
          </div>
          <div v-else-if="dimmingOnly" class="alert alert-warning small py-2 mb-0">
            <i class="bi bi-exclamation-triangle me-1"></i>
            The schedule is active and dimming the display
            <span v-if="scheduleWindowLabel">({{ scheduleWindowLabel }})</span>.
            Set night brightness to <code>0</code> to sleep instead of dimming.
          </div>
        </div>
      </div>
    </div>

    <!-- ====== Fine-tune schedule ====== -->
    <div id="group-sleep-advanced" class="card mb-3 p-3">
      <p class="section-heading"><i class="bi bi-sliders me-2"></i>Fine-tune schedule</p>

      <div v-if="!store.isAdvancedBrightness" class="text-muted small mb-0">
        Choose <strong>Fine-tune</strong> above to hold several brightness
        steps through the day. While <strong>Simple</strong> is selected, the
        single sleep window above applies instead.
      </div>

      <div v-show="store.isAdvancedBrightness">
      <div class="form-text text-muted small mb-2">
        Each row sets the brightness from its time until the next row; the
        last row holds overnight until the first. A brightness of
        <code>0</code> puts the unit in standby and stops polling.
      </div>

      <div v-if="store.ui.scheduleAdvancedActive" class="alert alert-warning small mt-2 mb-2 py-2">
        <i class="bi bi-exclamation-triangle me-1"></i>
        The brightness schedule is currently active - showing
        {{ store.formatTime(store.ui.scheduleAdvancedActive.time) }}
        &rarr; {{ store.ui.scheduleAdvancedActive.brightness }}.
      </div>

      <div class="table-responsive">
        <table class="table table-sm align-middle mb-2" style="max-width:420px">
          <thead class="table-light">
            <tr>
              <th scope="col" style="width:45%">Time</th>
              <th scope="col" style="width:35%">Brightness</th>
              <th scope="col" class="text-end" style="width:20%"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in store.screenScheduleAdvanced" :key="row.id">
              <td>
                <input type="time" class="form-control form-control-sm"
                       :class="{ 'is-invalid': !store.scheduleRowValid(row) }"
                       v-model="row.time" @change="store.resortSchedule()"
                       :aria-label="'Schedule time ' + ($index + 1)" />
                <div class="invalid-feedback small">
                  Enter a time that isn't already used by another row.
                </div>
              </td>
              <td>
                <select class="form-select form-select-sm" v-model.number="row.brightness"
                        :aria-label="'Brightness ' + ($index + 1)">
                  <option :value="0">0 (off)</option>
                  <option :value="1">1</option>
                  <option :value="2">2</option>
                  <option :value="3">3</option>
                  <option :value="4">4</option>
                  <option :value="5">5</option>
                </select>
              </td>
              <td class="text-end">
                <button type="button" class="btn btn-sm btn-outline-danger"
                        :aria-label="'Remove schedule entry ' + ($index + 1)"
                        @click="store.removeScheduleRow(row.id)">
                  <i class="bi bi-x-lg"></i>
                </button>
              </td>
            </tr>
            <tr v-if="!store.screenScheduleAdvanced.length">
              <td colspan="3" class="text-muted small">
                No schedule entries - the
                <a href="#brightness_mode_simple" role="button"
                   @click.prevent="store.config.brightness_mode = 'simple'">simple schedule</a>
                above applies instead.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <button type="button" class="btn btn-sm btn-outline-primary"
              :disabled="store.screenScheduleAdvanced.length >= 48"
              @click="store.addScheduleRow()">
        <i class="bi bi-plus-lg me-1"></i>Add
      </button>

      <input type="hidden" name="screen_schedule_advanced_json"
             :value="store.scheduleAdvancedJson()" />
      </div>
    </div>
    </div>
  `,
});
