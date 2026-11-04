"""Tests for utilities/scene_manager.py - priority-based scene dispatch."""

from unittest.mock import MagicMock

from utilities.scene_manager import SceneManager


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
