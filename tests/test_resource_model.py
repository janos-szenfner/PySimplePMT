from datetime import date
import json
import tempfile
import unittest
from pathlib import Path

from gantt_app.resource_model import (
    DAYS, DaysOffRange, Resource, ResourceRepository, ResourceType,
    SchedulePattern, TeamPool,
    capacity_from_entry, default_daily_capacity,
)


class TestResourceModel(unittest.TestCase):
    def resource(self, resource_id="res_1", resource_type=ResourceType.NAMED,
                 **values):
        defaults = {
            "name": "John Doe",
            "role_type": "QA Manager",
            "weekly_capacity_hours": 40,
            "cost_per_hour": 75,
        }
        defaults.update(values)
        return Resource(id=resource_id, resource_type=resource_type, **defaults)

    def test_resource_round_trip_preserves_enum_and_mappings(self):
        resource = self.resource(
            team_memberships={"team_1": 0.6},
            assigned_project_ids=["Project A", "Project B"],
        )

        restored = Resource.from_dict(resource.to_dict())

        self.assertEqual(restored, resource)
        self.assertIs(restored.resource_type, ResourceType.NAMED)

    def test_days_off_ranges_round_trip_with_a_resource(self):
        resource = self.resource(days_off=[DaysOffRange(
            date(2026, 8, 10), date(2026, 8, 20), "Summer Vacation")])

        restored = Resource.from_dict(resource.to_dict())

        self.assertEqual(restored.days_off, resource.days_off)
        self.assertEqual(restored.days_off[0].reason, "Summer Vacation")

    def test_days_off_range_rejects_an_end_before_its_start(self):
        with self.assertRaises(ValueError):
            DaysOffRange(date(2026, 8, 20), date(2026, 8, 10), "Invalid")

    def test_resource_rejects_team_type_and_invalid_numbers(self):
        with self.assertRaises(ValueError):
            self.resource(resource_type=ResourceType.TEAM)
        with self.assertRaises(ValueError):
            self.resource(weekly_capacity_hours=-1)
        with self.assertRaises(ValueError):
            self.resource(team_memberships={"team_1": 1.01})

    def test_dynamic_team_capacity_uses_member_percentages(self):
        team = TeamPool(id="team_1", name="Core QA")
        full_time = self.resource(team_memberships={"team_1": 0.6})
        placeholder = self.resource(
            "res_2", ResourceType.GENERIC, name="QA Engineer #1",
            weekly_capacity_hours=30,
            team_memberships={"team_1": 0.5},
        )

        self.assertEqual(
            team.calculate_effective_capacity([full_time, placeholder]), 39)

    def test_fixed_team_capacity_overrides_members(self):
        team = TeamPool(id="team_1", name="Core QA",
                        is_fixed_capacity=True, fixed_hours=160)

        self.assertEqual(team.calculate_effective_capacity([self.resource()]), 160)

    def test_team_allocation_accepts_percentages_and_zero_detaches(self):
        repository = ResourceRepository()
        repository.add_resource(self.resource())
        repository.add_team(TeamPool(id="team_1", name="Core QA"))

        repository.set_team_allocation("res_1", "team_1", 60)
        self.assertEqual(repository.resources["res_1"].team_memberships,
                         {"team_1": 0.6})

        repository.set_team_allocation("res_1", "team_1", 0)
        self.assertEqual(repository.resources["res_1"].team_memberships, {})
        with self.assertRaises(ValueError):
            repository.set_team_allocation("res_1", "team_1", 101)

    def test_removing_team_cleans_every_resource_membership(self):
        repository = ResourceRepository()
        repository.add_team(TeamPool(id="team_1", name="Core QA"))
        repository.add_resource(self.resource(
            team_memberships={"team_1": 0.6}))

        repository.remove_team("team_1")

        self.assertNotIn("team_1", repository.teams)
        self.assertEqual(repository.resources["res_1"].team_memberships, {})

    def test_generic_swap_preserves_identity_and_allocations(self):
        repository = ResourceRepository()
        generic = self.resource(
            "placeholder", ResourceType.GENERIC,
            name="DevOps Engineer #1", role_type="DevOps",
            assigned_project_ids=["Project A"],
            team_memberships={"team_1": 0.4},
        )
        named = self.resource(
            "person", name="Jane Smith", role_type="Senior DevOps",
            weekly_capacity_hours=32, cost_per_hour=90,
            assigned_project_ids=["Project B"],
        )
        repository.add_resource(generic)
        repository.add_resource(named)

        replacement = repository.swap_generic("placeholder", "person")

        self.assertEqual(replacement.id, "placeholder")
        self.assertEqual(replacement.name, "Jane Smith")
        self.assertIs(replacement.resource_type, ResourceType.NAMED)
        self.assertEqual(replacement.team_memberships, {"team_1": 0.4})
        self.assertEqual(replacement.assigned_project_ids,
                         ["Project A", "Project B"])
        self.assertIn("person", repository.resources)

    def test_standard_full_week_weekend_and_continuous_defaults(self):
        self.assertEqual(list(default_daily_capacity(
            SchedulePattern.STANDARD).values()), [8, 8, 8, 8, 8, 0, 0])
        self.assertAlmostEqual(sum(default_daily_capacity(
            SchedulePattern.FULL_WEEK).values()), 40)
        self.assertEqual(list(default_daily_capacity(
            SchedulePattern.WEEKEND_ONLY).values()), [0, 0, 0, 0, 0, 8, 8])
        self.assertEqual(list(default_daily_capacity(
            SchedulePattern.CONTINUOUS).values()), [24] * 7)

    def test_capacity_units_recalculate_daily_weekly_and_fte(self):
        weekly = capacity_from_entry(SchedulePattern.STANDARD, 20,
                                     "Weekly Hours")
        daily = capacity_from_entry(SchedulePattern.WEEKEND_ONLY, 12,
                                    "Daily Hours")
        fte = capacity_from_entry(SchedulePattern.FULL_WEEK, 1.5, "FTE")

        self.assertEqual(list(weekly.values()), [4, 4, 4, 4, 4, 0, 0])
        self.assertEqual(list(daily.values()), [0, 0, 0, 0, 0, 12, 12])
        self.assertAlmostEqual(sum(fte.values()), 60)

    def test_custom_daily_grid_drives_weekly_capacity_and_fte(self):
        resource = self.resource()

        resource.set_daily_capacity(dict(zip(DAYS, [8, 4, 8, 4, 0, 0, 0])))

        self.assertIs(resource.schedule_pattern, SchedulePattern.CUSTOM)
        self.assertEqual(resource.weekly_capacity_hours, 24)
        self.assertEqual(resource.fte, 0.6)

    def test_daily_workload_flags_only_the_overbooked_day(self):
        resource = self.resource()

        status = resource.workload_status({"mon": 10, "tue": 0})

        self.assertTrue(status["mon"]["overallocated"])
        self.assertEqual(status["mon"]["percentage"], 125)
        self.assertFalse(status["tue"]["overallocated"])

    def test_workload_by_calendar_date_uses_that_weekdays_capacity(self):
        resource = self.resource()

        status = resource.workload_status_for_dates({
            date(2026, 8, 31): 10,
            "2026-09-05": 2,
        })

        self.assertEqual(status["2026-08-31"]["percentage"], 125)
        self.assertTrue(status["2026-08-31"]["overallocated"])
        self.assertEqual(status["2026-09-05"]["capacity"], 0)
        self.assertTrue(status["2026-09-05"]["overallocated"])

    def test_team_daily_capacity_applies_each_member_split(self):
        team = TeamPool(id="team_1", name="Core QA")
        john = self.resource(team_memberships={"team_1": 0.5})
        weekend = self.resource(
            "res_2", ResourceType.GENERIC, name="Weekend QA",
            schedule_pattern=SchedulePattern.WEEKEND_ONLY,
            daily_capacity_hours=dict(zip(DAYS, [0, 0, 0, 0, 0, 12, 12])),
            team_memberships={"team_1": 0.25})

        daily = team.calculate_daily_capacity([john, weekend])

        self.assertEqual(list(daily.values()), [4, 4, 4, 4, 4, 3, 3])
        self.assertEqual(team.calculate_effective_capacity([john, weekend]), 26)

    def test_fixed_team_uses_its_own_daily_schedule(self):
        team = TeamPool(
            id="team_1", name="Operations", is_fixed_capacity=True,
            schedule_pattern=SchedulePattern.CONTINUOUS,
            fixed_daily_hours=dict.fromkeys(DAYS, 24))

        self.assertEqual(list(team.calculate_daily_capacity([]).values()),
                         [24] * 7)
        self.assertEqual(team.calculate_effective_capacity([]), 168)
        self.assertEqual(team.fixed_fte, 4.2)

    def test_generic_placeholder_names_increment_by_role(self):
        repository = ResourceRepository()
        repository.add_resource(self.resource(
            resource_type=ResourceType.GENERIC,
            name="DevOps Placeholder #1", role_type="DevOps"))

        self.assertEqual(repository.next_placeholder_name("DevOps"),
                         "DevOps Placeholder #2")
        self.assertEqual(repository.next_placeholder_name("QA"),
                         "QA Placeholder #1")

    def test_resource_operations_are_logged(self):
        repository = ResourceRepository()
        resource = self.resource()
        team = TeamPool(id="team_1", name="Core QA")

        with self.assertLogs("gantt_app.resource_model", level="INFO") as logs:
            repository.add_resource(resource)
            repository.add_team(team)
            repository.set_team_allocation(resource.id, team.id, 50)
            repository.remove_resource(resource.id)
            repository.remove_team(team.id)

        text = "\n".join(logs.output)
        self.assertIn("Added named resource", text)
        self.assertIn("allocation", text)
        self.assertIn("Removed resource", text)
        self.assertIn("Removed resource team", text)

    def test_legacy_resource_gains_a_standard_daily_schedule(self):
        data = self.resource().to_dict()
        data.pop("schedule_pattern")
        data.pop("daily_capacity_hours")

        restored = Resource.from_dict(data)

        self.assertIs(restored.schedule_pattern, SchedulePattern.STANDARD)
        self.assertEqual(list(restored.daily_capacity_hours.values()),
                         [8, 8, 8, 8, 8, 0, 0])

    def test_repository_persists_and_loads_resources_and_teams(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.json"
            repository = ResourceRepository(path)
            repository.add_resource(self.resource(
                assigned_project_ids=["Project A"]))
            repository.add_team(TeamPool(id="team_1", name="Core QA"))
            repository.set_team_allocation("res_1", "team_1", 25)

            repository.save_to_file()
            loaded = ResourceRepository(path)
            loaded.load_from_file()

            self.assertEqual(loaded.resources, repository.resources)
            self.assertEqual(loaded.teams, repository.teams)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))[
                "resources"][0]["resource_type"], "named")

    def test_repository_rejects_non_object_or_malformed_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.json"
            repository = ResourceRepository(path)
            for contents in ("[]", '{"resources": {}}',
                             '{"resources": [{}]}'):
                path.write_text(contents, encoding="utf-8")
                with self.subTest(contents=contents), self.assertRaises(ValueError):
                    repository.load_from_file()

    def test_missing_repository_file_loads_an_empty_pool(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = ResourceRepository(Path(directory) / "missing.json")
            repository.add_resource(self.resource())

            repository.load_from_file()

            self.assertEqual(repository.resources, {})
            self.assertEqual(repository.teams, {})


if __name__ == "__main__":
    unittest.main()
