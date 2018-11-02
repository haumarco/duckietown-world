# coding=utf-8

import os

import numpy as np
from comptests import comptest, run_module_tests, get_comptests_output_dir
from contracts import contract
from numpy.testing import assert_almost_equal

from duckietown_world import LaneSegment, RectangularArea, PlacedObject, SE2Transform
from duckietown_world.seqs.tsequence import SampledSequence
from duckietown_world.svg_drawing import draw_static
from duckietown_world.world_duckietown.differential_drive_dynamics import DifferentialDriveDynamicsParameters, \
    WheelVelocityCommands
from duckietown_world.world_duckietown.duckiebot import DB18
from duckietown_world.world_duckietown.lane_segment import get_distance_two
from duckietown_world.world_duckietown.map_loading import load_map
from duckietown_world.world_duckietown.tile import get_lane_poses, GetLanePoseResult
from duckietown_world.world_duckietown.tile_template import load_tile_types


def same_point(a, b):
    assert_almost_equal(a.p, b.p)
    assert_almost_equal(a.theta, b.theta)


@comptest
def lane_pose2():
    templates = load_tile_types()

    for name, ls in templates.items():
        if not isinstance(ls, LaneSegment):
            continue

        print(ls.get_lane_lengths())
        length = ls.get_lane_length()

        # first pose is the first control point
        lp0 = ls.lane_pose(along_lane=0.0, relative_heading=0.0, lateral=0.0)
        t0 = ls.SE2Transform_from_lane_pose(lp0)

        p0 = ls.control_points[0]
        same_point(p0, t0)

        # at 1 pose it is the second control point
        lp1 = ls.lane_pose(along_lane=length, relative_heading=0.0, lateral=0.0)
        t1 = ls.SE2Transform_from_lane_pose(lp1)

        p1 = ls.control_points[-1]
        same_point(p1, t1)

        l1 = length * 0.2
        l2 = length * 0.3
        d = l2 - l1


@comptest
def lane_pose3():
    templates = load_tile_types()

    for name, ls in templates.items():
        if not isinstance(ls, LaneSegment):
            continue

        length = ls.get_lane_length()

        # first pose is the first control point
        l1 = length * 0.3
        l2 = length * 0.4
        d = l2 - l1

        lp1 = ls.lane_pose(along_lane=l1, relative_heading=0.0, lateral=0.0)
        lp2 = ls.lane_pose(along_lane=l2, relative_heading=0.0, lateral=0.0)

        q1 = ls.SE2Transform_from_lane_pose(lp1).as_SE2()
        q2 = ls.SE2Transform_from_lane_pose(lp2).as_SE2()

        d2 = get_distance_two(q1, q2)

        assert_almost_equal(d, d2, decimal=3)


@comptest
def lane_pose4():
    templates = load_tile_types()

    for name, ls in templates.items():
        if not isinstance(ls, LaneSegment):
            continue
        print(name)

        lp1 = ls.lane_pose_random()
        # print('lp1: %s' % lp1)
        q1 = ls.SE2Transform_from_lane_pose(lp1)
        # print('q1: %s' % q1)
        lp2 = ls.lane_pose_from_SE2Transform(q1, tol=0.001)

        # print('lp2: %s' % lp2)
        assert_almost_equal(lp1.along_lane, lp2.along_lane, decimal=3)
        assert_almost_equal(lp1.lateral, lp2.lateral, decimal=3)
        assert_almost_equal(lp1.relative_heading, lp2.relative_heading, decimal=3)


@comptest
def center_point1():
    outdir = get_comptests_output_dir()
    templates = load_tile_types()

    for k, v in templates.items():
        if isinstance(v, LaneSegment):

            area = RectangularArea((-2, -2), (3, 3))
            dest = os.path.join(outdir, k)

            N = len(v.control_points)
            betas = list(np.linspace(-2, N + 1, 20))
            betas.extend(range(N))
            betas = sorted(betas)
            transforms = []
            for timestamp in betas:
                beta = timestamp
                p = v.center_point(beta)
                # print('%s: %s' % (beta, geo.SE2.friendly(p)))

                transform = SE2Transform.from_SE2(p)
                transforms.append(transform)

            c = SampledSequence(betas, transforms)
            v.set_object('a', PlacedObject(), ground_truth=c)
            draw_static(v, dest, area=area)


@comptest
def lane_pose_test1():
    outdir = get_comptests_output_dir()

    dw = load_map('udem1')

    area = RectangularArea((0, 0), (3, 3))

    v = 5
    s = [
        (1.0, WheelVelocityCommands(0.1 * v, 0.1 * v)),
        (2.0, WheelVelocityCommands(0.1 * v, 0.4 * v)),
        (4.0, WheelVelocityCommands(0.1 * v, 0.4 * v)),
        (5.0, WheelVelocityCommands(0.1 * v, 0.2 * v)),
        (6.0, WheelVelocityCommands(0.1 * v, 0.1 * v)),
    ]
    commands_sequence = SampledSequence.from_iterator(s)

    commands_sequence = commands_sequence.upsample(5)
    factory = reasonable_duckiebot()
    q0 = geo.SE2_from_translation_angle([1.8, 0.7], 0)
    poses_sequence = get_robot_trajectory(factory, q0, commands_sequence)
    transforms_sequence = poses_sequence.transform_values(SE2Transform.from_SE2)

    db = DB18()
    dw.set_object('duckiebot', db, ground_truth=transforms_sequence)

    class GetClosestLane(object):
        def __init__(self):
            # self.previous = None
            self.no_matches_for = []

        def __call__(self, transform):
            poses = list(get_lane_poses(dw, transform))
            if not poses:
                self.no_matches_for.append(transform)
                return None
            #
            # print(["/".join(_.lane_segment_fqn) for _ in poses])
            # if len(poses) == 1:
            #     closest = poses[0]
            # else:
            #     # more than one to choose from
            #
            #     if self.previous is not None:
            #         for _ in poses:
            #             if _.lane_segment_fqn == self.previous.lane_segment_fqn:
            #                 closest = _
            #                 break
            #         else:
            #             closest = sorted(poses, key=lambda _: _.lane_pose.distance_from_center)[0]
            #     else:
            #         closest = sorted(poses, key=lambda _: _.lane_pose.distance_from_center)[0]

            s = sorted(poses, key=lambda _: np.abs(_.lane_pose.relative_heading))
            res = {}
            for _ in s:
                name = "/".join(_.lane_segment_fqn)
                res[name] = _
            #
            # print("/".join(closest.lane_segment_fqn))
            # self.previous = closest
            return res

    # @contract(x=GetLanePoseResult)
    # def get_center_point(x):
    #     return x.center_point

    lane_pose_results = poses_sequence.transform_values(GetClosestLane())
    # center_points = lane_pose_results.transform_values(get_center_point)
    # dw.set_object('center_point', PlacedObject(), ground_truth=center_points)

    for i, (timestamp, name2pose) in enumerate(lane_pose_results):
        for name, lane_pose_result in name2pose.items():
            lane_segment = lane_pose_result.lane_segment
            rt = lane_pose_result.lane_segment_transform
            s = SampledSequence([timestamp], [rt])
            dw.set_object('ls%s-%s' % (i, name), lane_segment, ground_truth=s)

    draw_static(dw, outdir, area=area)


import geometry as geo


def integrate_commands(s0, commands_sequence):
    states = [s0]
    timestamps = commands_sequence.timestamps
    t0 = timestamps[0]
    yield t0, s0
    for i in range(len(timestamps) - 1):
        dt = timestamps[i + 1] - timestamps[i]
        commands = commands_sequence.values[i]
        s_prev = states[-1]
        s_next = s_prev.integrate(dt, commands)
        states.append(s_next)
        t = timestamps[i + 1]
        yield t, s_next


def get_robot_trajectory(factory, q0, commands_sequence):
    assert isinstance(commands_sequence, SampledSequence)
    t0 = commands_sequence.timestamps[0]

    # initialize trajectory
    c0 = q0, geo.se2.zero()
    s0 = factory.initialize(c0=c0, t0=t0)

    states_sequence = SampledSequence.from_iterator(integrate_commands(s0, commands_sequence))
    f = lambda _: _.TSE2_from_state()[0]
    poses_sequence = states_sequence.transform_values(f)
    return poses_sequence


def reasonable_duckiebot():
    radius = 0.1
    radius_left = radius
    radius_right = radius
    wheel_distance = 0.5
    dddp = DifferentialDriveDynamicsParameters(radius_left=radius_left, radius_right=radius_right,
                                               wheel_distance=wheel_distance)
    return dddp


if __name__ == '__main__':
    run_module_tests()
