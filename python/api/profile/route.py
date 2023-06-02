from http import HTTPStatus

from flask import Blueprint, Response, make_response

from api.profile.validator import user_should_exists_or_return_http_status_forbidden
from models import Profile, User
from storage.util import TunnelCode, is_file_exists, read_file_bytes
from util import make_simple_error_response

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


@profile_bp.route("/<string:name>", methods=["GET"])
@user_should_exists_or_return_http_status_forbidden
def fetch_profile(name: str) -> Response:
    profile: Profile = _get_user_profile_by_name(name)

    payload: dict[str, str] = {
        "user_uid": profile.user_uid,
        "email": profile.email,
        "school": profile.school,
        "bio": profile.bio
    }

    return make_response(payload)

@profile_bp.route("/avatar/<string:name>", methods=["GET"])
@user_should_exists_or_return_http_status_forbidden
def fetch_profile_avatar(name: str):
    profile: Profile = _get_user_profile_by_name(name)
    user_uid: str = profile.user_uid

    img_type: str = profile.img_type
    img_binaries: bytes = read_file_bytes(f"{user_uid}.{img_type}", TunnelCode.USER_AVATER)

    response: Response = make_response(img_binaries)
    response.headers.set('Content-Type', 'image/jpeg')
    return response

def _get_user_profile_by_name(name: str) -> Profile:
    user: User | None = User.query.filter_by(
        handle=name
    ).first()
    assert user is not None

    profile: Profile | None = Profile.query.filter_by(
        user_uid=user.user_uid
    ).first()
    assert profile is not None

    return profile
