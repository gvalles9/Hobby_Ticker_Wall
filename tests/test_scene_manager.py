"""Tests for utilities/scene_manager.py - priority-based scene dispatch."""

from unittest.mock import MagicMock

from utilities.scene_manager import SceneManager, scene_label


def _make_scene(priority, has_data=False, active=False):
    """Create a mock scene with the given priority and state."""
    scene = MagicMock()
    scene.priority = priority
    scene.debug_name = None
    scene.has_data.return_value = has_data
    scene.active.return_value = active
    scene.poll = MagicMock()
    scene.draw = MagicMock()
    scene.on_enter = MagicMock()
    scene.reset = MagicMock()
    return scene


class TestSceneManagerRegistration:
    def test_register_single_scene(self):
        sm = SceneManager()
        scene = _make_scene(1)
        sm.register(scene)
        assert len(sm.scenes) == 1

    def test_register_multiple_sorted_by_priority(self):
        sm = SceneManager()
        low = _make_scene(1)
        high = _make_scene(5)
        mid = _make_scene(3)
        sm.register(low)
        sm.register(high)
        sm.register(mid)
        assert sm.scenes == [low, mid, high]

    def test_no_scenes_kick_is_noop(self):
        sm = SceneManager()
        sm.kick()  # should not raise


class TestSceneManagerDispatch:
    def test_fallback_when_no_data(self):
        sm = SceneManager()
        fallback = _make_scene(0, has_data=False)
        high = _make_scene(5, has_data=False)
        sm.register(fallback)
        sm.register(high)
        sm.kick()
        fallback.on_enter.assert_called_once()
        fallback.draw.assert_called_once()

    def test_high_priority_with_data_preempts_fallback(self):
        sm = SceneManager()
        fallback = _make_scene(0, has_data=False)
        high = _make_scene(5, has_data=True)
        sm.register(fallback)
        sm.register(high)
        sm.kick()
        high.on_enter.assert_called_once()
        high.draw.assert_called_once()

    def test_higher_priority_with_data_preempts_active(self):
        sm = SceneManager()
        fallback = _make_scene(0)
        mid = _make_scene(3, active=True)
        high = _make_scene(5, has_data=True)
        sm.register(fallback)
        sm.register(mid)
        sm.register(high)
        sm.kick()
        high.on_enter.assert_called_once()

    def test_active_scene_not_preempted_by_lower_priority_data(self):
        sm = SceneManager()
        fallback = _make_scene(0)
        mid = _make_scene(3, has_data=True, active=True)
        high = _make_scene(5, active=True)
        sm.register(fallback)
        sm.register(mid)
        sm.register(high)
        sm.kick()
        # high is active and highest priority - should be drawn
        high.draw.assert_called_once()

    def test_same_scene_not_re_entered(self):
        sm = SceneManager()
        fallback = _make_scene(0)
        sm.register(fallback)
        sm.kick()
        sm.kick()  # second kick, same scene
        # on_enter should only be called once (on first kick)
        fallback.on_enter.assert_called_once()
        # draw should be called twice
        assert fallback.draw.call_count == 2

    def test_poll_called_on_all_scenes(self):
        sm = SceneManager()
        s1 = _make_scene(1, has_data=True)
        s2 = _make_scene(2)
        sm.register(s1)
        sm.register(s2)
        sm.kick()
        s1.poll.assert_called_once()
        s2.poll.assert_called_once()

    def test_debug_scene_forces_available_scene_over_higher_priority_scene(self):
        sm = SceneManager()
        idle = _make_scene(0, has_data=True, active=True)
        idle.debug_name = "idle"
        satellite = _make_scene(2, has_data=True)
        satellite.debug_name = "satellite"
        flight = _make_scene(1, has_data=True)
        flight.debug_name = "flight"
        for scene in (idle, flight, satellite):
            sm.register(scene)

        sm.kick(debug_scene="flight")

        flight.on_enter.assert_called_once()
        flight.draw.assert_called_once()
        satellite.draw.assert_not_called()

    def test_debug_scene_with_no_data_falls_back_to_normal_dispatch(self):
        sm = SceneManager()
        idle = _make_scene(0, has_data=True, active=True)
        idle.debug_name = "idle"
        flight = _make_scene(1, has_data=False)
        flight.debug_name = "flight"
        sm.register(idle)
        sm.register(flight)

        sm.kick(debug_scene="flight")

        idle.draw.assert_called_once()
        flight.draw.assert_not_called()


class TestReplaceFallback:
    def test_replacement_stays_at_index_zero(self):
        sm = SceneManager()
        old = _make_scene(0)
        high = _make_scene(5)
        new = _make_scene(0)
        sm.register(old)
        sm.register(high)

        sm.replace_fallback(new)

        assert sm.scenes[0] is new
        assert sm.scenes[1] is high

    def test_current_fallback_is_replaced_and_entered(self):
        sm = SceneManager()
        old = _make_scene(0)
        sm.register(old)
        sm.kick()
        assert sm.current_scene is old
        old.on_enter.reset_mock()

        new = _make_scene(0)
        sm.replace_fallback(new)

        assert sm.current_scene is new
        new.on_enter.assert_called_once()
        old.on_enter.assert_not_called()

    def test_current_high_priority_scene_is_untouched(self):
        sm = SceneManager()
        old = _make_scene(0)
        high = _make_scene(5, has_data=True)
        sm.register(old)
        sm.register(high)
        sm.kick()
        assert sm.current_scene is high

        new = _make_scene(0)
        sm.replace_fallback(new)

        assert sm.current_scene is high
        assert sm.scenes[0] is new
        new.on_enter.assert_not_called()

    def test_empty_manager_registers_the_scene(self):
        sm = SceneManager()
        new = _make_scene(0)

        sm.replace_fallback(new)

        assert sm.scenes == [new]

    def test_replacing_with_the_same_scene_is_a_no_op(self):
        sm = SceneManager()
        old = _make_scene(0)
        sm.register(old)
        sm.kick()
        old.on_enter.reset_mock()

        sm.replace_fallback(old)

        assert sm.scenes == [old]
        old.on_enter.assert_not_called()


class TestSceneFailureContainment:
    def test_poll_failure_does_not_stop_other_scenes(self):
        sm = SceneManager()
        first = _make_scene(1)
        second = _make_scene(2)
        first.poll.side_effect = RuntimeError("boom")
        sm.register(first)
        sm.register(second)

        sm.kick()

        second.poll.assert_called_once()

    def test_failing_scene_is_skipped_and_idle_takes_over(self):
        sm = SceneManager()
        idle = _make_scene(0)
        flight = _make_scene(5, has_data=True)
        flight.draw.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(flight)

        sm.kick()

        assert sm.current_scene is idle
        idle.on_enter.assert_called_once()
        idle.draw.assert_called_once()

    def test_failing_scene_is_not_retried_during_quarantine(self):
        sm = SceneManager()
        idle = _make_scene(0)
        flight = _make_scene(5, has_data=True)
        flight.draw.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(flight)

        sm.kick()
        sm.kick()

        assert flight.draw.call_count == 1
        assert idle.draw.call_count == 2

    def test_scene_is_retried_after_quarantine_expires(self):
        sm = SceneManager(quarantine_seconds=0)
        idle = _make_scene(0)
        flight = _make_scene(5, has_data=True)
        flight.draw.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(flight)

        sm.kick()
        flight.draw.side_effect = None
        sm.kick()

        assert sm.current_scene is flight
        assert flight.draw.call_count == 2

    def test_has_data_failure_is_treated_as_no_data(self):
        sm = SceneManager()
        idle = _make_scene(0)
        flight = _make_scene(5)
        flight.has_data.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(flight)

        sm.kick()

        idle.draw.assert_called_once()

    def test_active_failure_is_treated_as_not_active(self):
        sm = SceneManager()
        idle = _make_scene(0)
        mid = _make_scene(3, has_data=True)
        high = _make_scene(5, active=True)
        high.active.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(mid)
        sm.register(high)

        sm.kick()

        mid.draw.assert_called_once()

    def test_on_enter_failure_falls_back_to_idle(self):
        sm = SceneManager()
        idle = _make_scene(0)
        flight = _make_scene(5, has_data=True)
        flight.on_enter.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(flight)

        sm.kick()

        assert sm.current_scene is idle
        flight.draw.assert_not_called()
        idle.draw.assert_called_once()

    def test_fallback_failure_does_not_raise_or_draw_twice(self):
        sm = SceneManager()
        idle = _make_scene(0)
        idle.draw.side_effect = RuntimeError("boom")
        sm.register(idle)

        sm.kick()

        assert idle.draw.call_count == 1

    def test_error_callback_receives_the_scene_label(self):
        labels = []
        sm = SceneManager(on_scene_error=labels.append)
        idle = _make_scene(0)
        flight = _make_scene(5, has_data=True)
        flight.debug_name = "flight"
        flight.draw.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(flight)

        sm.kick()

        assert labels == ["flight"]

    def test_error_callback_failure_does_not_escape(self):
        sm = SceneManager(on_scene_error=MagicMock(side_effect=RuntimeError))
        idle = _make_scene(0)
        flight = _make_scene(5, has_data=True)
        flight.draw.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(flight)

        sm.kick()

        idle.draw.assert_called_once()

    def test_forced_debug_scene_failure_falls_back(self):
        sm = SceneManager()
        idle = _make_scene(0)
        idle.debug_name = "idle"
        flight = _make_scene(5, has_data=True)
        flight.debug_name = "flight"
        flight.draw.side_effect = RuntimeError("boom")
        sm.register(idle)
        sm.register(flight)

        sm.kick(debug_scene="flight")

        idle.draw.assert_called_once()


class TestSceneLabel:
    def test_uses_the_debug_name(self):
        class _Named:
            debug_name = "indy_top3"

        assert scene_label(_Named()) == "indy top3"

    def test_falls_back_to_the_class_name(self):
        class ImageScene:
            pass

        assert scene_label(ImageScene()) == "Image"
