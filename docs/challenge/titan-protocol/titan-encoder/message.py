from __future__ import annotations


from dataclasses import dataclass, field
from enum import IntEnum

START_OF_FRAME = "$"
END_OF_FRAME = "|"


class CommandIds(IntEnum):
    Ping = 1
    HouseKeeping = 10
    Log = 12


@dataclass
class Message:

    command_id: CommandIds
    sequence: int
    timestamp: int

    payload: tuple[int, ...] = field(default_factory=list)

    def encode_to_str(self) -> str:
        payload = ";".join(str(c) for c in self.payload)
        return (
            f"{START_OF_FRAME}"
            f"{self.command_id};{self.sequence};{self.timestamp};{payload};{END_OF_FRAME}\n"
        )

    def from_str(input_str: str) -> Message:
        assert input_str[0] == START_OF_FRAME
        assert input_str[-1] == END_OF_FRAME

        fields = input_str[1:-1].split(";")

        return Message(
            command_id=int(fields[0]),
            sequence=int(fields[3]),
            timestamp=int(fields[4]),
            payload=(int(f) for f in fields[5:] if f != ""),
        )

    def __str__(self) -> str:
        message_type = self.__class__.__name__
        if self.command_id in iter(CommandIds):
            message_type = CommandIds(self.command_id).name

        return (
            f"{message_type}("
            f"{self.timestamp:5}: {self.command_id} (s:{self.sequence:3}), {self.payload}"
            ")"
        )


@dataclass
class HouseKeepingPayload:

    status: int
    theta: int
    phi: int
    intensity: int
    temperature: int

    def __str__(self) -> str:
        status_string = "   OK" if self.status == 0 else "FAULT"

        return f"Status: {status_string}, Pos: ({self.theta/1000:05.2f};{self.phi/1000:05.2f}) I={self.intensity}, T: {self.temperature/1000}"
