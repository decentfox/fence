from cdislogging import get_logger
import flask
from flask_restful import Resource

from fence.auth import login_user
from fence.errors import InternalError, Unauthorized
from fence.models import IdentityProvider
from fence.config import config


logger = get_logger(__name__)


class ShibbolethLoginStart(Resource):
    def get(self):
        """
        The login flow is:
        user
        -> {fence}/login/shib?redirect={portal}
        -> user login at {nih_shibboleth_idp}
        -> nih idp POST to fence shibboleth and establish a shibboleth sp
           session
        -> redirect to {fence}/login/shib/login that sets up fence session
        -> redirect to portal
        """
        redirect_url = flask.request.args.get("redirect")
        if redirect_url:
            flask.session["redirect"] = redirect_url

        # figure out which IDP to target with shibboleth
        # check out shibboleth docs here for more info:
        # https://wiki.shibboleth.net/confluence/display/SP3/SSO
        entityID = flask.request.args.get("shib_idp")
        print("entityID", entityID)
        flask.session["entityID"] = entityID
        actual_redirect = config["BASE_URL"] + "/login/shib/login"
        if not entityID or entityID == "urn:mace:incommon:nih.gov":
            # default to SSO_URL from the config which should be NIH login
            return flask.redirect(config["SSO_URL"] + actual_redirect)
        print(
            "ShibbolethLoginStart redirect",
            config["BASE_URL"]
            + "/Shibboleth.sso/Login?entityID={}&target={}".format(
                entityID, actual_redirect
            ),
        )
        return flask.redirect(
            config["BASE_URL"]
            + "/Shibboleth.sso/Login?entityID={}&target={}".format(
                entityID, actual_redirect
            )
        )


class ShibbolethLoginFinish(Resource):
    def get(self):
        """
        Complete the shibboleth login.
        """
        shib_header = config.get("SHIBBOLETH_HEADER")
        if not shib_header:
            raise InternalError("Missing shibboleth header configuration")

        print("************************************")
        print("************************************")
        print('shib_header', shib_header)
        print("flask.request.headers", flask.request.headers)
        print("************************************")
        print("************************************")

        # eppn stands for eduPersonPrincipalName
        username = flask.request.headers.get("eppn")
        if not username:
            persistent_id = flask.request.headers.get(shib_header)
            username = persistent_id.split("!")[-1] if persistent_id else None
            if not username:
                raise Unauthorized("Unable to retrieve username for Shibboleth results")
        idp = IdentityProvider.itrust
        if flask.session.get("entityID"):
            idp = flask.session.get("entityID")
        print("ShibbolethLoginFinish idp", idp)
        login_user(flask.request, username, idp)
        if flask.session.get("redirect"):
            return flask.redirect(flask.session.get("redirect"))
        return "logged in"
