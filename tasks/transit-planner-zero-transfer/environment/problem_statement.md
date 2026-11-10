# Issue: Trip planner prefers a slower route, and some trip times are too long

## Problem Description

Riders report two symptoms:

- Harbor to Museum is planned as a direct Green line trip of 19 minutes. Riders say that changing lines is faster.
- Some trip times are a few minutes longer than the timetable suggests.

## Expected Behavior

- The planner returns the fastest trip between any two stations.
- A change between lines costs the time listed in `data/network.json`, including a listed time of 0.
- A change with no time in `data/network.json` keeps the documented 4-minute default.

## Visibility

This file is grader-side context. It is not copied into the task image. The agent receives only `instruction.md` (a short report in a developer's words) and the starter repo, so that the task measures diagnosis as well as the fix.
