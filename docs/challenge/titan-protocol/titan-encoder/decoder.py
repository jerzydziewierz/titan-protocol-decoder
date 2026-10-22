#!/usr/bin/env python3

from __future__ import annotations


from message import CommandIds, Message, HouseKeepingPayload

PING_PERIOD_NOMINAL = 500
# PING_PERIOD_WARNING
# PING_PERIOD_FAULT


def main():

    messages = []
    with open("byte-stream-1.txt") as f:
        for line in f:
            try:
                m = Message.from_str(line.strip())
                messages.append(m)
            except AssertionError:
                print(f"Invalid message: {line.strip()}")

    print("")

    last_ping_timestamp = 0
    last_hk_timestamp = 0
    for m in messages:
        if m.command_id == CommandIds.Ping.value:
            this_ping_timestamp = m.timestamp
            dt = this_ping_timestamp - last_ping_timestamp
            dt_error = dt - PING_PERIOD_NOMINAL

            warning_flag = "!" if dt_error > 50 else " "

            print(
                f"Ping({m.sequence:03}): t = {this_ping_timestamp:5} (dt = {dt:4} / {dt_error:4}{warning_flag})"
            )

            last_ping_timestamp = this_ping_timestamp
        if m.command_id == CommandIds.HouseKeeping:
            this_hk_timestamp = m.timestamp
            dt = this_hk_timestamp - last_hk_timestamp

            print(
                f"HK({m.sequence:03})  : t = {this_hk_timestamp:5} (dt = {dt:5}) {HouseKeepingPayload(*m.payload)}"
            )

            last_hk_timestamp = this_hk_timestamp


if __name__ == "__main__":
    main()
