# goip-configurator
Tool to monitor and reconfigure the GOIP-1 gateway.

Just clone and run the start script from your platform folder (win/mac/rasp[berry]).
Options supported by main.py:  
--windows / --raspberry / --mac - for running on the specified platform (needed for PhantomJS driver);
--prod - option to be used on the production environment only.
  
You should create your own secret/secrets.py file with the mandatory settings defined:
 - IS_PROD      - whether environment is test or prod;
 - IP           - IP address of the GoIP gateway (caller);
 - SIP          - SIP number to be assigned to the GoIP gateway;
 - SIP_PASS     - SIP password to be used with the number from above;
 - SENDER_PHONE - full phone number to be used as "CALLER NUMBER";
 - USER         - username to login to the GoIP gateway;
 - PASS         - password to use with the username from above;
 - SMPP_USER    - username to be used for the SMPP connection;
 - SMPP_SECRET  - password to use with the username from above;
 - TEL_CHAT     - telegram chat id to connect to;
 - TEL_KEY      - telegram key to be used with the chat id from above;
 - ALLOWED_USERS - users allowed to interact with bot and issue commands to it.

You may also specify these mandatory settings directly in the const.py file.
All other settings are stored in src/const.py file and may be changed to your taste.
Enjoy :)
