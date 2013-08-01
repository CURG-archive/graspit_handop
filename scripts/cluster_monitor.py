import smtplib


def send_email(sender, to, content, password):
	"""
    @brief Send an email (or text message) through a gmail account.

    @param sender - "from" field of email.
    @param to - recepient email address
    @param content - contents of email
    @param password - password of account

    @returns A list of new hands derived from the old hands.
    """
	server = smtplib.SMTP("smtp.gmail.com", 587)
	server.starttls()
	server.login(sender, password)

	server.sendmail(sender, to, content)