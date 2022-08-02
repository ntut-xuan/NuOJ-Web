import traceback
from flask import *
import time
import os
import auth_util
import database_util
from error_code import error_dict, ErrorCode
import setting_util
from datetime import datetime
from uuid import uuid4
from tunnel_code import TunnelCode
import re

profile_page = Blueprint('profile_page', __name__)

def updateUserProfile(handle):
	# Name all lowercase
	handle = handle.lower()

	# Query User UID from Database
	database_data = database_util.command_execute("SELECT user_uid from `user` where handle=%s", (handle))

	# Return HANDLE_NOT_FOUND if user handle is not found
	if len(database_data) == 0:
		return error_dict(ErrorCode.HANDLE_NOT_FOUND)

	# Get User UID
	user_uid = database_data[0]["user_uid"]

	# Check user session is valid, otherwise return REQUIRE_AUTHORIZATION
	SID = request.cookies.get("SID")
	if (SID not in session) or (session[SID]["handle"].lower() != handle):
		return error_dict(ErrorCode.REQUIRE_AUTHORIZATION)

	# Check data is all valid
	# User Email: should exist and changeable, should check email is valid or not.
	# User School: allow null value, should use some method to improve it, limit 70 words.
	# User Bio: allow null value, limit 200 words.
	put_data = request.json
	email_data = put_data["email"]
	school_data = put_data["school"]
	bio_data = put_data["bio"]

	# Check Email is valid or not
	email_valid = bool(re.match("^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$", email_data))
	if not email_valid:
		return error_dict(ErrorCode.EMAIL_INVALID)

	# Check User School is valid or not
	if len(school_data) > 70:
		return error_dict(ErrorCode.INVALID_DATA, "School name too long.")

	# Check User Bio is valid or not
	if len(bio_data) > 200:
		return error_dict(ErrorCode.INVALID_DATA, "Bio too long.")

	# Create / Update User Data in storage, it should be exist when user complete register.
	if not database_util.file_storage_tunnel_exist(user_uid + ".json", TunnelCode.USER_PROFILE):
		return error_dict(ErrorCode.UNEXCEPT_ERROR, "User profile storage data not found.")

	data = json.loads(database_util.file_storage_tunnel_read(user_uid + ".json", TunnelCode.USER_PROFILE))
	
	data["email"] = email_data
	data["school"] = school_data
	data["bio"] = bio_data

	database_util.file_storage_tunnel_write(user_uid + ".json", json.dumps(data), TunnelCode.USER_PROFILE)

	return {"status": "OK"}

@profile_page.route("/profile/<name>", methods=["GET", "PUT"])
@profile_page.route("/profile/<name>/", methods=["GET", "PUT"])
def returnProfilePageWithName(name):

	if request.method == "PUT":
		return json.dumps(updateUserProfile(name))

	# Check user exist
	count = database_util.command_execute("SELECT COUNT(*) FROM `user` WHERE handle=%s", (name))[0]["COUNT(*)"]

	if count == 0:
		abort(404)

	# Fetch user infomation
	user_data = database_util.command_execute("SELECT role FROM `user` WHERE handle=%s", (name))[0]
	admin = user_data["role"]
	handle = name
	school = "未知"
	accountType = "使用者" if admin == 0 else "管理員"
	
	problem_data = database_util.command_execute("SELECT * FROM `problem` WHERE problem_author=%s", (handle))
	problems = []

	for data in problem_data:
		if not database_util.file_storage_tunnel_exist(data["problem_pid"] + ".json", TunnelCode.PROBLEM):
			problems.append({"color": "green", "state": "公開", "title": "---", "token": data["problem_pid"]})
			continue
		problem_storage_data = json.loads(database_util.file_storage_tunnel_read(data["problem_pid"] + ".json", TunnelCode.PROBLEM))
		problems.append({"color": "green", "state": "公開", "title": problem_storage_data["problem_content"]["title"], "token": data["problem_pid"]})
	
	return render_template("profile.html", **locals())
