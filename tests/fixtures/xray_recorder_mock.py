from aws_xray_sdk.core import AsyncAWSXRayRecorder
from aws_xray_sdk.core.models.segment import Segment
from typing import List


class XRayRecorderMock(AsyncAWSXRayRecorder):
    stored_segment: Segment
    stored_subsegments: List[Segment]

    def begin_segment(
        self,
        name: str = None,
        trace_id: str = None,
        parent_id: str = None,
        sampling: int = None,
    ) -> Segment:
        self.stored_segment = super().begin_segment(
            name=name, traceid=trace_id, parent_id=parent_id, sampling=sampling
        )
        return self.stored_segment

    def begin_subsegment(self, name: str = None, namespace: str = "local") -> Segment:
        if not hasattr(self, "stored_subsegments"):
            self.stored_subsegments = []

        self.stored_subsegments.append(
            super().begin_subsegment(name=name, namespace=namespace)
        )
        return self.stored_subsegments[-1]
