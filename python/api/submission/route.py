import json
from typing import Any
from uuid import uuid4

from flask import Blueprint, make_response, request

from api.auth.validator import validate_jwt_is_exists_or_return_unauthorized, validate_jwt_is_valid_or_return_unauthorized
from api.submission.validate import validate_judge_result_payload_or_return_bad_request, validate_submission_should_exists_or_return_forbidden
from api.submission.dataclass import JudgeDetail, JudgeStatus, JudgeResult
from database import db
from models import Submission, Verdict, VerdictErrorComment
from storage.util import TunnelCode, write_file

submission_bp = Blueprint("submission", __name__, url_prefix="/api/submission")


@submission_bp.route("/<int:submission_id>/result", methods=["POST"])
@validate_judge_result_payload_or_return_bad_request
@validate_submission_should_exists_or_return_forbidden
def add_verdict_route(submission_id: int):
    payload: dict[str, Any] | None = request.get_json(silent=True)
    assert payload is not None
    judge_result: JudgeResult = JudgeResult(**payload)

    judge_verdict: str = judge_result.data.status
    judge_details: list[JudgeDetail] = judge_result.data.judge_detail
    memory_usage: int = _fetch_memory_average_usage(judge_result.data.status, judge_details)
    time_usage: int = _fetch_time_average_usage(judge_result.data.status, judge_details)
    tracker_uid: str = _fetch_tracker_uid_from_submission_id(submission_id)
    error_id: int | None = _make_verdict_error(judge_result.data.status, judge_result.data.message, judge_details)

    verdict: Verdict = Verdict(
        verdict=judge_verdict,
        tracker_uid=tracker_uid,
        error_id=error_id,
        memory_usage=memory_usage,
        time_usage=time_usage,
    )
    db.session.add(verdict)
    db.session.commit()

    write_file(f"{tracker_uid}.json", json.dumps(payload), TunnelCode.VERDICT)

    return make_response({"status": "OK"})


def _make_verdict_error(status: JudgeStatus, message: str, judge_details: list[JudgeDetail]) -> int | None:
    if status == JudgeStatus.AC.value:
        return None

    failed_testcase_index: int = _fetch_failed_testcase_index(judge_details)
    log: str = message
    verdictErrorMessage: VerdictErrorComment = VerdictErrorComment(
        failed_testcase_index=failed_testcase_index, message=log
    )

    db.session.add(verdictErrorMessage)
    db.session.commit()
    
    id: int = verdictErrorMessage.id
    return id


def _fetch_tracker_uid_from_submission_id(submission_id: int):
    submission: Submission | None = Submission.query.filter_by(id=submission_id).first()
    assert submission is not None

    return submission.tracker_uid


def _fetch_failed_testcase_index(judge_details: list[JudgeDetail]):
    for index in range(len(judge_details)):
        if judge_details[index].verdict != "AC":
            return index
    return -1


def _fetch_memory_average_usage(status: JudgeStatus, judge_details: list[JudgeDetail]):
    memory: int = 0

    if len(judge_details) == 0:
        return memory
    
    if _is_solution_error(status):
        return memory

    for judge_detail in judge_details:
        memory += judge_detail.runtime_info.submit.memory

    return memory // len(judge_details)


def _fetch_time_average_usage(status: JudgeStatus, judge_details: list[JudgeDetail]):
    time: float = 0

    if len(judge_details) == 0:
        return time
    
    if _is_solution_error(status):
        return time

    for judge_detail in judge_details:
        time += judge_detail.runtime_info.submit.time

    return time / len(judge_details)


def _is_solution_error(status: JudgeStatus):
    return status == JudgeStatus.SMLE.value or status == JudgeStatus.SRE.value or status == JudgeStatus.STLE.value