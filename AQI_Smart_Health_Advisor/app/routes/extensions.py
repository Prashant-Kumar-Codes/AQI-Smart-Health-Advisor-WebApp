from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
import requests
import psycopg2
from flask_mail import Message
from app import mail
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import os
import json