# Boot to the login screen
from vmtest import run
from vmtest.i18n import I18n
from vmtest.command import WaitFor, FindText, Text, Keys, PowerOff, Screenshot

run(
    # Wait for boot
    WaitFor(FindText(I18n("motd"))),
    WaitFor(FindText(I18n("login"))),
    # Log in
    Text("root\n"),
    Screenshot(),
    # Clear console
    Text("clear\n"),
    # Log out
    Keys("ctrl-d"),
    WaitFor(FindText(I18n("login"))),
    # Poweroff
    PowerOff(),
)
