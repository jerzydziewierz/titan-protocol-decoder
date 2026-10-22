#!/usr/bin/env python3
#
# USe this script to generate and mutate messages.
#
# Without any options, this script will generate a sequence of messages
# composed of Ping packets and House Keeping packets. These are sent at
# regular intervals (with a small jitter).
#
# This sequence can be made more interesting by
#
# - simulating an overloaded system (adds a incremental delay to messages)
# - simulatingh a defective sensor (sets the status field to non-zero)
# - truncating the messages (to check how robust the code is)
#
# These options can be enabled and disabled by setting the relevant global
# variables.
#
# The length of the capture can be changed by changing the `DURATION` variable.
#

from __future__ import annotations

import random

from dataclasses import astuple
from message import CommandIds, Message, HouseKeepingPayload

# Enable or disable features
SYSTEM_OVERLOAD = True
SENSOR_FAILURE = False
BAD_LINK = False

MILLI = 1000

START_TIME = 0 * MILLI
DURATION = 10 * MILLI
END_TIME = START_TIME + DURATION

FILE_NAME = "tital-protocol-messages.txt"


def with_jitter(t, lower=-100, upper=250):
    return max(0, t + random.randrange(lower, upper))


def system_ok_scenario():
    ping_messages = []
    for t in range(START_TIME, END_TIME, 500):
        ping_messages.append(
            Message(
                command_id=CommandIds.Ping,
                sequence=0,
                timestamp=with_jitter(t, -10, 10),
            )
        )

    housekeeping_messages = []
    for t in range(START_TIME, END_TIME, 1000):

        sim_progress = (t - START_TIME) / DURATION
        sun_pos_theta = 12 + sim_progress * 35.76
        sun_pos_phi = -90 + sim_progress * 17.654

        m = Message(
            command_id=CommandIds.HouseKeeping,
            sequence=0,
            timestamp=with_jitter(t, -10, 10),
            payload=astuple(
                HouseKeepingPayload(
                    status=0,
                    theta=int(sun_pos_theta * 1000),
                    phi=int(sun_pos_phi * 1000),
                    intensity=with_jitter(73, -5, 5),
                    temperature=-30000 + int(with_jitter(t * 0.1, -100, 100)),
                )
            ),
        )

        housekeeping_messages.append(m)

    # Make a random element have a fault code
    m = random.choice(housekeeping_messages)
    payload = HouseKeepingPayload(*m.payload)
    payload.status = 255
    m.payload = astuple(payload)

    messages = sorted(
        [*ping_messages, *housekeeping_messages], key=lambda x: x.timestamp
    )
    for i, m in enumerate(messages):
        m.sequence = i

    return messages


def make_overloaded(telemetry_messages):
    running_delay = 0
    for m in telemetry_messages:
        if m.command_id != CommandIds.Ping.value:
            continue

        running_delay += random.randint(100, 200)
        m.timestamp += running_delay

    return telemetry_messages


def make_sensor_defective(telemetry_stream):
    for m in telemetry_stream:
        if m.command_id != CommandIds.HouseKeeping.value:
            continue

        payload = HouseKeepingPayload(*m.payload)
        payload.phi = random.randrange(-90000, 90000)
        payload.theta = random.randrange(-90000, 90000)

        m.payload = astuple(payload)


def corrupt_maybe(message):
    should_corrupt = random.random() > 0.9
    if should_corrupt:
        drop_amount = random.randrange(0, int(len(message) / 2))
        message = message[:-drop_amount] + "\n"

    return message


def main():

    telemetry_stream = system_ok_scenario()
    if SYSTEM_OVERLOAD:
        telemetry_stream = make_overloaded(telemetry_stream)

    if SENSOR_FAILURE:
        telemetry_stream = make_sensor_defective(telemetry_stream)

    with open("byte-stream-1.txt", "w+") as f:
        for m in telemetry_stream:
            encoded = m.encode_to_str()
            if BAD_LINK:
                encoded = telemetry_stream = corrupt_maybe(encoded)

            if len(encoded) > 0:
                f.write(encoded)

    print("With: ")
    print(f"  - System Overloaded? {SYSTEM_OVERLOAD}")
    print(f"  - Sensor Failed    ? {SENSOR_FAILURE}")
    print(f"  - Bad Link         ? {BAD_LINK}")

    print(f"Generated and mutated {len(telemetry_stream)} messages")


if __name__ == "__main__":
    main()
