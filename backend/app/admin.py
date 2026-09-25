"""Local administrator bootstrap; password is prompted without shell history."""
import argparse
import getpass

from app.api.dependencies.security import get_human_auth_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    args = parser.parse_args()
    password = getpass.getpass("Initial administrator password (12+ characters): ")
    if not 12 <= len(password) <= 256 or password != getpass.getpass("Confirm password: "):
        parser.error("password length invalid or confirmation differs")
    from app.api.routers.auth import UserCreate
    user = UserCreate(username=args.username, password=password, role="administrator")
    get_human_auth_service().create_user(user.username, user.password, user.role, "local-bootstrap")
    print("Administrator created. Sign in through the web interface.")


if __name__ == "__main__":
    main()
