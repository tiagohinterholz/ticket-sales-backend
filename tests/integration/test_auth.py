from fastapi.testclient import TestClient


def register(client: TestClient, email: str = "user@example.com", **overrides):
    payload = {"email": email, "password": "s3cret-pass", "name": "Test User"}
    payload.update(overrides)
    return client.post("/auth/register", json=payload)


class TestRegister:
    def test_register_creates_customer_role_user(self, client: TestClient):
        response = register(client)

        assert response.status_code == 201
        assert response.json()["role"] == "CUSTOMER"

    def test_register_with_duplicate_email_returns_409(self, client: TestClient):
        register(client, email="dup@example.com")

        response = register(client, email="dup@example.com")

        assert response.status_code == 409


class TestLogin:
    def test_login_with_correct_credentials_returns_200_and_token(
        self, client: TestClient
    ):
        register(client, email="login-ok@example.com", password="right-pass")

        response = client.post(
            "/auth/login",
            json={"email": "login-ok@example.com", "password": "right-pass"},
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_with_wrong_password_returns_401_generic_error(
        self, client: TestClient
    ):
        register(client, email="login-wrongpw@example.com", password="right-pass")

        response = client.post(
            "/auth/login",
            json={"email": "login-wrongpw@example.com", "password": "wrong-pass"},
        )

        assert response.status_code == 401

    def test_login_with_nonexistent_email_returns_same_401_generic_error(
        self, client: TestClient
    ):
        register(client, email="login-wrongpw@example.com", password="right-pass")
        wrong_password_response = client.post(
            "/auth/login",
            json={"email": "login-wrongpw@example.com", "password": "wrong-pass"},
        )

        unknown_email_response = client.post(
            "/auth/login",
            json={"email": "never-registered@example.com", "password": "whatever"},
        )

        assert unknown_email_response.status_code == 401
        assert unknown_email_response.status_code == wrong_password_response.status_code
        assert unknown_email_response.json() == wrong_password_response.json()


class TestMe:
    def test_me_without_token_returns_401(self, client: TestClient):
        response = client.get("/auth/me")

        assert response.status_code == 401

    def test_me_with_valid_token_returns_current_user_data(self, client: TestClient):
        register(client, email="me@example.com", name="Me User")
        login_response = client.post(
            "/auth/login",
            json={"email": "me@example.com", "password": "s3cret-pass"},
        )
        token = login_response.json()["access_token"]

        response = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "me@example.com"
        assert body["name"] == "Me User"
        assert body["role"] == "CUSTOMER"
