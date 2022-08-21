import traceback
from flask import *
import time
import os
from auth_util import jwt_valid, jwt_decode
import database_util
from error_code import error_dict, ErrorCode
import setting_util
from datetime import datetime
from uuid import uuid4
from tunnel_code import TunnelCode
from functools import wraps
import re
import json
import base64

profile_page = Blueprint('profile_page', __name__)

def require_session(func):
	@wraps(func)
	def decorator(*args, **kwargs):
		SID = request.cookies.get("SID")

		if not jwt_valid(SID):
			resp = Response(json.dumps(error_dict(ErrorCode.REQUIRE_AUTHORIZATION)), mimetype="application/json")
			resp.set_cookie("SID", value = "", expires=0)
			return resp
		
		return func(*args, **kwargs)
	return decorator

def updateUserProfile(cookies, handle, put_data):

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
	if not jwt_valid(cookies):
		return error_dict(ErrorCode.REQUIRE_AUTHORIZATION)
	
	cookies_data = jwt_decode(cookies)
	cookies_handle = cookies_data["handle"]

	if cookies_handle != handle:
		return error_dict(ErrorCode.REQUIRE_AUTHORIZATION, "Cookies user handle not equals to the handle of put data.")

	# Check data is all valid
	# User Email: should exist and changeable, should check email is valid or not.
	# User School: allow null value, should use some method to improve it, limit 70 words.
	# User Bio: allow null value, limit 200 words.1
	if ("email" not in put_data) or ("school" not in put_data) or ("bio" not in put_data):
		return error_dict(ErrorCode.INVALID_DATA)

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

	# Check need to update data or insert a new data
	count = database_util.command_execute("SELECT COUNT(*) from `profile` where user_uid=%s", (user_uid))[0]["COUNT(*)"]

	if count == 0:
		database_util.command_execute("INSERT INTO `profile`(user_uid, email, school, bio) VALUES(%s, %s, %s, %s)", (user_uid, email_data, school_data, bio_data))
	else:
		database_util.command_execute("UPDATE `profile` SET email=%s, school=%s, bio=%s WHERE user_uid=%s", (email_data, school_data, bio_data, user_uid))

	return {"status": "OK"}

@profile_page.route("/profile/<name>", methods=["GET", "PUT"])
@profile_page.route("/profile/<name>/", methods=["GET", "PUT"])
def returnProfilePageWithName(name):
	if request.method == "PUT":
		put_data = request.json
		cookies = request.cookies.get("SID")
		return json.dumps(updateUserProfile(cookies, name, put_data))
	return render_template("profile.html", **locals())

@profile_page.route("/upload_img",methods=["PUT"])
@require_session
def update_user_img():
	try:	
		SID = request.cookies.get("SID")
		handle = jwt_decode(SID)["handle"]
	except:
		return "please login", 400

	# Check user exist
	count = database_util.command_execute("SELECT COUNT(*) FROM `user` WHERE handle=%s", (handle))[0]["COUNT(*)"]

	if count == 0:
		abort(400)

	user_uid = database_util.command_execute("SELECT * FROM `user` WHERE handle=%s", (handle))[0]["user_uid"]

	# 如有舊資料則刪除

	old_img_type = database_util.command_execute("SELECT img_type FROM `profile` WHERE user_uid=%s", (user_uid))[0]["img_type"]
	if(old_img_type != None):
		database_util.file_storage_tunnel_del(user_uid+"."+old_img_type,TunnelCode.USER_AVATER)

	# 讀取新資料
	put_data = request.json
	raw_data = put_data['img']
	file_name = user_uid+"."+put_data['type']

	i=0
	while(1):
		if(raw_data[i]==","):
			break
		i+=1
	img_data = raw_data[i+1:]
	img_data = base64.b64decode(img_data)

	# updata database 

	database_util.byte_storage_tunnel_write(file_name,img_data)
	database_util.command_execute("UPDATE `profile` SET img_type=%s WHERE user_uid=%s" , (put_data['type'] , user_uid))
	return {"status" : "OK"}

@profile_page.route("/get_profile",methods=["GET"])
@require_session
def getUserInfo():

	# vertify user

	try:	
		SID = request.cookies.get("SID")
		handle = jwt_decode(SID)["handle"]
	except:
		return "please login", 400

	# Check user exist
	count = database_util.command_execute("SELECT COUNT(*) FROM `user` WHERE handle=%s", (handle))[0]["COUNT(*)"]

	if count == 0:
		abort(400)

	# Fetch user infomation
	user_data = database_util.command_execute("SELECT * FROM `user` WHERE handle=%s", (handle))[0]
	user_uid = user_data["user_uid"]
	email = user_data["email"]
	accountType = "User" if user_data["role"] == 0 else "admin"
	
	profile_data = database_util.command_execute("SELECT * FROM `profile` WHERE user_uid=%s", (user_uid))

	if(len(profile_data)==0):
		abort(400)
	else:
		profile_data = profile_data[0]

	school = "" if profile_data["school"] == None else profile_data["school"]  
	bio = "" if profile_data["bio"] == None else profile_data["bio"]
	img = "/static/logo-black.svg" if profile_data["img_type"] == None else ("/storage/user_avater/"+user_uid+"."+profile_data["img_type"])

	resp = {
		"main":{
			"img" : img,
			"handle" : handle,
			"accountType":accountType
		},
		"sub":{
			"email" : email,	
			"school" : school,
			"bio" : bio
		}
	}
	return resp 

@profile_page.route("/profile_problem_list",methods=["GET"])
@require_session
def get_problem_list():
	try:	
		SID = request.cookies.get("SID")
		handle = jwt_decode(SID)["handle"]
	except:
		return "please login", 400
	
	args = request.args
	number_of_problem = int(args["numbers"])
	offset = int(args["from"])

	problems = database_util.command_execute("select * from problem where problem_author=%s limit %s offset %s;",(handle,number_of_problem,offset))
	result =[]
	i=0
	for problem in problems:
		problem_pid = problem["problem_pid"]
		problem_raw_data = database_util.file_storage_tunnel_read("%s.json"%problem_pid,TunnelCode.PROBLEM)

		if( len(problem_raw_data)!= 0):

			problem_json = json.loads(problem_raw_data)

			permission = False

			if(problem_json["basic_setting"]["permission"] == "1"):
				permission = True
			
			subdata = {"id":i, "title" : problem_json["problem_content"]["title"], "permission" :	permission , "author" : problem["problem_author"], "problem_pid":problem_pid}
			result.append(subdata)
			i+=1
	return {"data":result}

@profile_page.route("/profile_problem_setting",methods=["GET"])
@require_session
def get_problem_list_setting():
	try:	
		SID = request.cookies.get("SID")
		handle = jwt_decode(SID)["handle"]
	except:
		return "please login", 400
	

	args = request.args


	count = database_util.command_execute("select count(*) from problem where problem_author = %s",(handle))
	response={
		"count":count[0]["count(*)"]
	}
	return response

@profile_page.route("/storage/<path:path>")
def returnStaticFile(path):
	return send_from_directory('../storage', path)