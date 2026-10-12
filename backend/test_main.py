import os
import tempfile
import unittest
import asyncio
import io
import time
from contextlib import closing
from email.message import Message
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from backend import main


class PersistenceRegressionTests(unittest.TestCase):
    def test_startup_preserves_existing_records_and_seeds_empty_tables(self):
        with tempfile.TemporaryDirectory(dir=os.path.dirname(__file__)) as directory:
            db_path = os.path.join(directory, "audit.db")
            with patch.object(main, "DB_PATH", db_path):
                main.init_db()
                with main.sqlite3.connect(db_path) as connection:
                    connection.execute("UPDATE farmer SET name = 'Test farmer' WHERE id = 1")
                    connection.execute("UPDATE crop SET variety = 'Test variety' WHERE id = 1")
                    connection.execute("UPDATE market SET price = 123.0 WHERE crop = 'Tomato'")
                    connection.execute("UPDATE storage SET name = 'Test storage' WHERE id = 1")
                    connection.execute("UPDATE weather SET temperature = 11 WHERE location = 'Bengaluru'")
                    connection.execute("UPDATE farming_task SET title = 'Test task' WHERE id = 1")
                    connection.execute("UPDATE notification SET title = 'Test notification' WHERE id = 1")
                    connection.execute("DELETE FROM news")
                    connection.commit()
                connection.close()
                main.init_db()
                with main.sqlite3.connect(db_path) as connection:
                    farmer = connection.execute("SELECT name FROM farmer WHERE id = 1").fetchone()[0]
                    crop = connection.execute("SELECT variety FROM crop WHERE id = 1").fetchone()[0]
                    market = connection.execute("SELECT price FROM market WHERE crop = 'Tomato' LIMIT 1").fetchone()[0]
                    storage = connection.execute("SELECT name FROM storage WHERE id = 1").fetchone()[0]
                    weather = connection.execute("SELECT temperature FROM weather WHERE location = 'Bengaluru' LIMIT 1").fetchone()[0]
                    task = connection.execute("SELECT title FROM farming_task WHERE id = 1").fetchone()[0]
                    notification = connection.execute("SELECT title FROM notification WHERE id = 1").fetchone()[0]
                    news_count = connection.execute("SELECT COUNT(*) FROM news").fetchone()[0]
                connection.close()
                self.assertEqual(farmer, "Test farmer")
                self.assertEqual(crop, "Test variety")
                self.assertEqual(market, 123.0)
                self.assertEqual(storage, "Test storage")
                self.assertEqual(weather, 11.0)
                self.assertEqual(task, "Test task")
                self.assertEqual(notification, "Test notification")
                self.assertGreater(news_count, 0)

    def test_existing_calendar_schema_is_migrated_without_dropping_rows(self):
        with tempfile.TemporaryDirectory(dir=os.path.dirname(__file__)) as directory:
            db_path = os.path.join(directory, "legacy.db")
            connection = main.sqlite3.connect(db_path)
            connection.execute("CREATE TABLE farming_task (id INTEGER PRIMARY KEY, title TEXT, crop TEXT, date TEXT, priority TEXT, completed INTEGER)")
            connection.execute("INSERT INTO farming_task VALUES (99, 'Keep this task', 'Tomato', '2026-10-10', 'Low', 0)")
            connection.commit()
            connection.close()
            with patch.object(main, "DB_PATH", db_path):
                main.init_db()
                row = main.fetch_all("SELECT title, data_source FROM farming_task WHERE id = 99")[0]
            self.assertEqual(row["title"], "Keep this task")
            self.assertEqual(row["data_source"], "DEMO DATA")


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory(dir=os.path.dirname(__file__))
        self.db_path = os.path.join(self.temp_directory.name, "auth.db")
        self.db_patch = patch.object(main, "DB_PATH", self.db_path)
        self.db_patch.start()
        main.init_db()
        self.client = TestClient(main.app)
        with main._auth_rate_limit_lock:
            main._auth_attempts.clear()

    def tearDown(self):
        self.client.close()
        self.db_patch.stop()
        self.temp_directory.cleanup()
        with main._auth_rate_limit_lock:
            main._auth_attempts.clear()

    def test_signup_login_profile_and_logout(self):
        signup = self.client.post("/api/auth/signup", json={
            "name": "  Test   Farmer ",
            "email": " FARMer@example.com ",
            "password": "Strong-password-123!",
        })
        self.assertEqual(signup.status_code, 201)
        account = signup.json()
        self.assertEqual(account["user"]["name"], "Test Farmer")
        self.assertEqual(account["user"]["email"], "farmer@example.com")
        self.assertNotIn("password_hash", account["user"])
        headers = {"Authorization": f"Bearer {account['access_token']}"}
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).json()["name"], "Test Farmer")
        updated = self.client.put("/api/auth/profile", headers=headers, json={"name": "Updated Farmer"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["name"], "Updated Farmer")
        logout = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_duplicate_email_and_invalid_credentials_are_rejected(self):
        payload = {"name": "Test Farmer", "email": "farmer@example.com", "password": "Strong-password-123!"}
        self.assertEqual(self.client.post("/api/auth/signup", json=payload).status_code, 201)
        duplicate = {**payload, "email": "FARMER@example.com"}
        self.assertEqual(self.client.post("/api/auth/signup", json=duplicate).status_code, 409)
        invalid_login = self.client.post("/api/auth/login", json={"email": payload["email"], "password": "incorrect"})
        self.assertEqual(invalid_login.status_code, 401)
        self.assertEqual(invalid_login.json()["detail"], "Email or password is incorrect.")

    def test_two_accounts_keep_identity_isolated_across_login_and_session_lookup(self):
        accounts = [
            {"name": "Asha Rao", "email": "asha@example.com", "password": "Strong-password-123!"},
            {"name": "Mohan Das", "email": "mohan@example.com", "password": "Strong-password-456!"},
        ]
        signup_results = [self.client.post("/api/auth/signup", json=account).json() for account in accounts]
        self.assertEqual([result["user"]["name"] for result in signup_results], ["Asha Rao", "Mohan Das"])

        first_login = self.client.post("/api/auth/login", json={"email": accounts[0]["email"], "password": accounts[0]["password"]})
        self.assertEqual(first_login.status_code, 200)
        first_headers = {"Authorization": f"Bearer {first_login.json()['access_token']}"}
        self.assertEqual(first_login.json()["user"]["name"], "Asha Rao")
        # /auth/me is the backend lookup used when a page restores its saved session.
        self.assertEqual(self.client.get("/api/auth/me", headers=first_headers).json()["name"], "Asha Rao")

        updated = self.client.put("/api/auth/profile", headers=first_headers, json={"name": "Asha Updated"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=first_headers).json()["name"], "Asha Updated")
        self.assertEqual(self.client.post("/api/auth/logout", headers=first_headers).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=first_headers).status_code, 401)

        second_login = self.client.post("/api/auth/login", json={"email": accounts[1]["email"], "password": accounts[1]["password"]})
        self.assertEqual(second_login.status_code, 200)
        second_headers = {"Authorization": f"Bearer {second_login.json()['access_token']}"}
        self.assertEqual(second_login.json()["user"]["name"], "Mohan Das")
        self.assertEqual(self.client.get("/api/auth/me", headers=second_headers).json()["name"], "Mohan Das")

    def test_legacy_account_without_a_name_uses_farmer_fallback(self):
        account = self.client.post("/api/auth/signup", json={
            "name": "Legacy Farmer", "email": "legacy@example.com", "password": "Strong-password-123!",
        }).json()
        with closing(main.sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE app_user SET name = '' WHERE id = ?", (account["user"]["id"],))
            connection.commit()

        headers = {"Authorization": f"Bearer {account['access_token']}"}
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).json()["name"], "Farmer")
        login = self.client.post("/api/auth/login", json={"email": "legacy@example.com", "password": "Strong-password-123!"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["user"]["name"], "Farmer")

    def test_signup_rejects_passwords_without_required_character_classes(self):
        response = self.client.post("/api/auth/signup", json={
            "name": "Test Farmer", "email": "weak@example.com", "password": "lowercasepassword1",
        })
        self.assertEqual(response.status_code, 422)

    def test_passwords_are_salted_and_not_stored_in_plain_text(self):
        payload = {"name": "Test Farmer", "email": "farmer@example.com", "password": "Strong-password-123!"}
        self.client.post("/api/auth/signup", json=payload)
        with closing(main.sqlite3.connect(self.db_path)) as connection:
            row = connection.execute("SELECT password_salt, password_hash FROM app_user").fetchone()
        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], payload["password"])
        self.assertNotEqual(row[1], payload["password"])
        self.assertNotEqual(row[0], row[1])

    def test_calendar_requires_login_and_scopes_new_tasks_to_the_owner(self):
        self.assertEqual(self.client.get("/api/calendar").status_code, 401)
        first = self.client.post("/api/auth/signup", json={
            "name": "First Farmer", "email": "first@example.com", "password": "Strong-password-123!",
        }).json()
        second = self.client.post("/api/auth/signup", json={
            "name": "Second Farmer", "email": "second@example.com", "password": "Strong-password-456!",
        }).json()
        first_headers = {"Authorization": f"Bearer {first['access_token']}"}
        second_headers = {"Authorization": f"Bearer {second['access_token']}"}
        payload = {"title": "Water field", "crop": "Tomato", "date": "2026-10-20", "priority": "High", "completed": False}
        created = self.client.post("/api/calendar/tasks", headers=first_headers, json=payload)
        self.assertEqual(created.status_code, 200)
        task_id = created.json()["id"]
        self.assertIn(task_id, [task["id"] for task in self.client.get("/api/calendar", headers=first_headers).json()])
        self.assertNotIn(task_id, [task["id"] for task in self.client.get("/api/calendar", headers=second_headers).json()])
        update = self.client.put(f"/api/calendar/tasks/{task_id}", headers=second_headers, json=payload)
        delete = self.client.delete(f"/api/calendar/tasks/{task_id}", headers=second_headers)
        self.assertEqual(update.status_code, 404)
        self.assertEqual(delete.status_code, 404)


class MandiIntegrationTests(unittest.TestCase):
    def setUp(self):
        with main._MANDI_CACHE_LOCK:
            main._MANDI_CACHE.clear()
        self.client = TestClient(main.app)

    def tearDown(self):
        with main._MANDI_CACHE_LOCK:
            main._MANDI_CACHE.clear()

    def _provider(self, payload):
        with main._MANDI_CACHE_LOCK:
            main._MANDI_CACHE.clear()
        with patch.object(main, "get_secret", return_value="https://mandi-api.onrender.com/v1"), \
             patch.object(main, "external_json", return_value=payload) as request:
            response = self.client.get("/api/markets/prices?state=Karnataka&commodity=Tomato")
        return response, request

    def test_success_envelope_is_mapped_and_source_unit_is_not_assumed(self):
        response, request = self._provider({"success": True, "data": [{
            "state": "Karnataka", "district": "Mysuru", "market": "Mysuru APMC",
            "commodity": "Tomato", "variety": "Local", "arrival_date": main.date.today().isoformat(),
            "min_price": 1800, "max_price": 2400, "modal_price": 2100,
            "fetched_at": "2026-10-10T04:00:00Z",
        }], "meta": {"count": 1}})
        self.assertEqual(response.status_code, 200)
        record = response.json()["data"][0]
        self.assertEqual(record["modal_price"], 2100)
        self.assertIsNone(record["source_price_unit"])
        self.assertIsNone(record["converted_modal_price"])
        self.assertFalse(record["price_compatible"])
        self.assertEqual(response.json()["freshness"], "current")
        self.assertEqual(request.call_args.kwargs["timeout"], 12)
        self.assertIn("state=Karnataka", request.call_args.args[0])
        self.assertIn("commodity=Tomato", request.call_args.args[0])
        self.assertEqual(response.json()["data_source"], "Mandi Price API")

    def test_tomato_prices_are_not_filtered_by_options_list(self):
        with patch.object(main, "get_secret", return_value="https://mandi-api.onrender.com/v1"), \
             patch.object(main, "external_json", side_effect=lambda url, **kwargs: (
                 {"success": True, "data": ["Karnataka"]} if url.endswith("/states") else
                 {"success": True, "data": ["Apple", "Arecanut"]} if "/commodities?" in url else
                 {"success": True, "data": [{"state": "Karnataka", "commodity": "Tomato", "arrival_date": "2026-10-10", "modal_price": 1800}], "meta": {}}
             )):
            options = self.client.get("/api/markets/options?state=Karnataka")
            prices = self.client.get("/api/markets/prices?state=Karnataka&commodity=Tomato")
        self.assertEqual(options.status_code, 200)
        self.assertNotIn("Tomato", options.json()["commodities"])
        self.assertEqual(prices.status_code, 200)
        self.assertEqual(len(prices.json()["data"]), 1)
        self.assertEqual(prices.json()["data"][0]["commodity"], "Tomato")
        self.assertEqual(prices.json()["data_source"], "Mandi Price API")

    def test_empty_records_and_missing_fields_are_returned_without_fabrication(self):
        empty, _ = self._provider({"success": True, "data": [], "meta": {"count": 0}})
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["data"], [])
        missing, _ = self._provider({"success": True, "data": [{"arrival_date": "bad-date"}], "meta": {}})
        self.assertEqual(missing.status_code, 200)
        self.assertNotIn("modal_price", missing.json()["data"][0])
        self.assertEqual(missing.json()["freshness"], "unknown")

    def test_stale_records_are_flagged_by_arrival_date(self):
        old_date = (main.date.today() - main.timedelta(days=8)).isoformat()
        response, _ = self._provider({"success": True, "data": [{"arrival_date": old_date}], "meta": {}})
        self.assertEqual(response.json()["freshness"], "stale")
        self.assertEqual(response.json()["latest_arrival_date"], old_date)

    def test_provider_timeout_is_sanitized(self):
        with patch.object(main, "get_secret", return_value="https://mandi-api.onrender.com/v1"), \
             patch.object(main, "external_json", side_effect=TimeoutError("private timeout detail")):
            response = self.client.get("/api/markets/prices?state=Karnataka&commodity=Tomato")
        self.assertEqual(response.status_code, 504)
        self.assertIn("timed out", response.json()["detail"])
        self.assertNotIn("private timeout detail", response.text)

    def test_rate_limit_and_http_errors_are_safe(self):
        for status, expected in [(429, 429), (500, 502)]:
            with self.subTest(status=status):
                error = main.urllib.error.HTTPError("https://provider.invalid", status, "internal", {}, None)
                with patch.object(main, "get_secret", return_value="https://mandi-api.onrender.com/v1"), \
                     patch.object(main, "external_json", side_effect=error):
                    response = self.client.get("/api/markets/prices?state=Karnataka&commodity=Tomato")
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("provider.invalid", response.text)
                error.close()

    def test_invalid_json_and_invalid_envelope_are_rejected(self):
        with patch.object(main, "get_secret", return_value="https://mandi-api.onrender.com/v1"), \
             patch.object(main, "external_json", side_effect=main.json.JSONDecodeError("bad", "{", 0)):
            invalid_json = self.client.get("/api/markets/prices?state=Karnataka&commodity=Tomato")
        self.assertEqual(invalid_json.status_code, 502)
        with patch.object(main, "get_secret", return_value="https://mandi-api.onrender.com/v1"), \
             patch.object(main, "external_json", return_value={"success": True, "data": {}}):
            invalid_envelope = self.client.get("/api/markets/prices?state=Karnataka&commodity=Tomato")
        self.assertEqual(invalid_envelope.status_code, 502)

    def test_explicit_quintal_unit_converts_and_preserves_original(self):
        record = main.normalize_mandi_record({"modal_price": 2100, "price_unit": "Rs/Quintal"})
        self.assertEqual(record["modal_price"], 2100)
        self.assertEqual(record["converted_modal_price"], 21)
        self.assertTrue(record["price_compatible"])

    def test_profit_calculation_accepts_kg_inputs(self):
        payload = main.ProfitRequest(crop="Tomato", quantity=100, current_price=20,
            expected_selling_price=25, transport_cost=100, storage_cost=0,
            production_cost=500, other_expenses=0, storage_duration_days=0)
        result = main.calculate_profit_scenarios(payload)
        self.assertEqual(result["sell_revenue"], 2000)
        self.assertEqual(result["store_revenue"], 2500)

    def test_options_envelope(self):
        with patch.object(main, "get_secret", return_value="https://mandi-api.onrender.com/v1"), \
             patch.object(main, "external_json", side_effect=[{"success": True, "data": ["Karnataka"]}, {"success": True, "data": ["Tomato"]}]):
            response = self.client.get("/api/markets/options?state=Karnataka")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["states"], ["Karnataka"])
        self.assertEqual(response.json()["commodities"], ["Tomato"])
class ProfitRegressionTests(unittest.TestCase):
    def test_storage_duration_multiplies_per_day_cost(self):
        request = main.ProfitRequest(quantity=10, current_price=5, expected_selling_price=7,
                                     transport_cost=2, storage_cost=3, storage_duration_days=4,
                                     production_cost=10, other_expenses=1)
        result = main.calculate_profit_scenarios(request)
        self.assertEqual(result["storage_total"], 12)
        self.assertEqual(result["sell_profit"], 37)
        self.assertEqual(result["store_profit"], 45)

    def test_profit_endpoint_reports_loss_and_zero_revenue_without_division_error(self):
        response = TestClient(main.app).post("/api/profit/calculate", json={
            "quantity": 10, "current_price": 0, "expected_selling_price": 0,
            "transport_cost": 5, "storage_cost": 0, "storage_duration_days": 0,
            "production_cost": 20, "other_expenses": 0,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revenue"], 0)
        self.assertEqual(response.json()["net_profit"], -25)
        self.assertEqual(response.json()["profit_percentage"], 0)

    def test_profit_rejects_negative_cost(self):
        with self.assertRaises(Exception):
            main.ProfitRequest(quantity=10, current_price=5, expected_selling_price=7,
                               transport_cost=-1, storage_cost=0)

    def test_decision_does_not_recommend_from_missing_inputs(self):
        result = main.score_to_decision(main.DecisionRequest())
        self.assertEqual(result["status"], "insufficient_data")
        self.assertTrue(result["missing_inputs"])
        self.assertEqual(result["confidence"], 0)

    def test_dashboard_has_no_market_placeholder_when_market_is_missing(self):
        def rows(query, params=()):
            if "FROM farmer" in query:
                return [{"id": 1, "name": "Sample farmer", "location": "Bengaluru", "preferred_language": "en", "farm_size": 2, "primary_crop": "Tomato"}]
            if "FROM crop" in query:
                return [{"id": 1, "name": "Tomato", "variety": "Sample", "planting_date": "2026-01-01", "expected_harvest_date": "2026-12-01", "current_stage": "Maturity", "quantity": 10}]
            return []

        with patch.object(main, "fetch_all", side_effect=rows), \
             patch.object(main, "get_weather", new=AsyncMock(return_value=[])), \
             patch.object(main, "get_market_rows", new=AsyncMock(return_value=[])), \
             patch.object(main, "get_market_trend_data", new=AsyncMock(return_value={"trend_available": False})), \
             patch.object(main, "get_storage", new=AsyncMock(return_value=[])):
            result = asyncio.run(main.build_dashboard_payload())
        self.assertEqual(result["market"], [])
        self.assertEqual(result["decision"]["status"], "insufficient_data")


class CalendarValidationTests(unittest.TestCase):
    def test_calendar_rejects_blank_required_text(self):
        response = TestClient(main.app).post("/api/calendar/tasks", json={
            "title": "   ", "crop": "Tomato", "date": "2026-10-10", "priority": "Low"
        })
        self.assertEqual(response.status_code, 422)

    def test_calendar_rejects_invalid_date(self):
        response = TestClient(main.app).post("/api/calendar/tasks", json={
            "title": "Irrigate field", "crop": "Tomato", "date": "not-a-date", "priority": "Low"
        })
        self.assertEqual(response.status_code, 422)


class CropDoctorTests(unittest.TestCase):
    def test_missing_key_returns_setup_error_without_fake_diagnosis(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        with patch.object(main, "get_secret", return_value=""):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("PLANTNET_API_KEY", raised.exception.detail)

    def test_invalid_key_format_is_rejected_without_provider_request(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        with patch.object(main, "get_secret", return_value="malformed key"), patch.object(main, "external_json") as request:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 503)
        request.assert_not_called()

    def test_wrong_image_signature_is_rejected(self):
        upload = UploadFile(filename="fake.jpg", file=io.BytesIO(b"not an image"), headers=Headers({"content-type": "image/jpeg"}))
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 400)

    def test_external_service_failure_is_an_error_not_a_diagnosis(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", side_effect=TimeoutError("offline")):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 504)
        self.assertIn("Pl@ntNet species identification failed", raised.exception.detail)

    def test_plantnet_uses_species_identification_and_maps_species_score(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        response_payload = {"bestMatch": "Solanum lycopersicum L.", "remainingIdentificationRequests": 499,
            "results": [
                {"score": 0.87, "species": {"scientificNameWithoutAuthor": "Solanum lycopersicum", "commonNames": ["Tomato"]}},
                {"score": 0.09, "species": {"scientificNameWithoutAuthor": "Solanum pimpinellifolium", "commonNames": ["Currant tomato"]}},
            ]}
        with patch.object(main, "get_secret", return_value="test-plantnet-secret"), \
             patch.object(main, "external_json", return_value=response_payload) as request:
            result = asyncio.run(main.analyze_crop(images=[upload], crop="Tomato", location="", organs=["leaf"]))
        args = request.call_args.args
        self.assertIn("/v2/identify/all?", args[0])
        self.assertIn(b'name="images"', args[2])
        self.assertIn(b'name="organs"', args[2])
        self.assertIn(b"leaf", args[2])
        self.assertEqual(args[3], 15)
        self.assertEqual(result["scientific_name"], "Solanum lycopersicum")
        self.assertEqual(result["identification_score"], 0.87)
        self.assertEqual(result["identification_score_percent"], 87.0)
        self.assertEqual(result["identified_species"]["score_percent"], 87.0)
        self.assertEqual(result["crop"], "Tomato")
        self.assertEqual(result["best_match"], "Solanum lycopersicum L.")
        self.assertEqual(result["candidates"][1]["name"], "Currant tomato")
        self.assertEqual(result["candidates"][1]["score_percent"], 9.0)
        self.assertEqual(result["remaining_identification_requests"], 499)
        self.assertEqual(result["disease_detection"], "unavailable")
        self.assertNotIn("possible_disease", result)
        self.assertIn("does not assess plant health", result["disclaimer"])

    def test_species_endpoint_returns_mapped_candidates_without_secret(self):
        payload = {"bestMatch": "Acer rubrum L.", "results": [{"score": 0.91, "species": {
            "scientificNameWithoutAuthor": "Acer rubrum", "commonNames": ["Red maple"]
        }}]}
        client = TestClient(main.app)
        with patch.object(main, "get_secret", return_value="private-plantnet-key"), \
             patch.object(main, "external_json", return_value=payload):
            response = client.post("/api/crop/analyze", files={"images": ("maple.jpg", bytes((255, 216, 255, 1)), "image/jpeg")}, data={"organs": "leaf"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["identified_species"]["scientific_name"], "Acer rubrum")
        self.assertEqual(response.json()["candidates"][0]["score_percent"], 91.0)
        self.assertNotIn("private-plantnet-key", response.text)

    def test_plantnet_bestmatch_is_used_only_when_candidates_are_unavailable(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "external_json", return_value={"results": [], "bestMatch": "Acer rubrum"}):
            result = asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(result["crop"], "Acer rubrum")
        self.assertIsNone(result["identification_score"])

    def test_plantnet_malformed_response_is_an_explicit_error(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "external_json", return_value={"unexpected": []}):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("unexpected species identification response", raised.exception.detail)

    def test_plantnet_quota_error_does_not_retry_and_is_sanitized(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        quota = main.urllib.error.HTTPError("https://provider.invalid", 429, "quota", {}, None)
        with patch.object(main, "get_secret", return_value="private-plantnet-key"), \
             patch.object(main, "external_json", side_effect=quota) as request:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("daily identification quota", raised.exception.detail)
        self.assertNotIn("private-plantnet-key", raised.exception.detail)
        request.assert_called_once()
        quota.close()

    def test_plantnet_auth_error_is_clear_and_not_retried(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        unauthorized = main.urllib.error.HTTPError("https://provider.invalid", 401, "unauthorized", {}, None)
        with patch.object(main, "get_secret", return_value="private-plantnet-key"), \
             patch.object(main, "external_json", side_effect=unauthorized) as request:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("rejected the configured API key", raised.exception.detail)
        self.assertNotIn("private-plantnet-key", raised.exception.detail)
        request.assert_called_once()
        unauthorized.close()

    def test_plantnet_malformed_json_is_a_sanitized_provider_error(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        malformed = main.json.JSONDecodeError("secret provider body", "{", 0)
        with patch.object(main, "get_secret", return_value="private-plantnet-key"), \
             patch.object(main, "external_json", side_effect=malformed):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.analyze_crop(images=[upload], crop="", location="", organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("invalid JSON", raised.exception.detail)
        self.assertNotIn("secret provider body", raised.exception.detail)

    def test_disease_screening_is_separate_uses_correct_route_and_maps_limited_results(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        response = {"remainingIdentificationRequests": 498, "results": [{"name": "1ABC", "description": "Possible leaf spot", "score": 0.66}]}
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "external_json", return_value=response) as request:
            result = asyncio.run(main.screen_crop_disease(images=[upload], organs=["leaf"]))
        args = request.call_args.args
        self.assertIn("/v2/diseases/identify?", args[0])
        self.assertIn(b'name="images"', args[2])
        self.assertIn(b'name="organs"', args[2])
        self.assertEqual(result["candidates"][0]["description"], "Possible leaf spot")
        self.assertEqual(result["candidates"][0]["score_percent"], 66.0)
        self.assertIn("not a diagnosis", result["disclaimer"])

    def test_disease_screening_access_denial_is_clear_and_not_retried(self):
        upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        forbidden = main.urllib.error.HTTPError("https://provider.invalid", 403, "forbidden", {}, None)
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "external_json", side_effect=forbidden) as request:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.screen_crop_disease(images=[upload], organs=["leaf"]))
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("disease screening is unavailable", raised.exception.detail)
        request.assert_called_once()
        forbidden.close()

    def test_missing_species_does_not_fall_back_to_submitted_tomato_crop(self):
        upload = UploadFile(filename="maple.jpg", file=io.BytesIO(bytes((255, 216, 255, 1))), headers=Headers({"content-type": "image/jpeg"}))
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "external_json", return_value={"results": []}):
            result = asyncio.run(main.analyze_crop(images=[upload], crop="Tomato", location="", organs=["leaf"]))
        self.assertIsNone(result["crop"])
        self.assertIsNone(result["identified_species"])
        self.assertIsNone(result["identification_score"])
        self.assertEqual(result["status"], "No plant species identified")
        self.assertEqual(result["disease_detection"], "unavailable")


class GNewsIntegrationTests(unittest.TestCase):
    def setUp(self):
        main._gnews_cache.clear()
        main._gnews_last_request = 0.0

    def test_gnews_maps_real_article_fields_and_keeps_key_out_of_response(self):
        payload = {"articles": [{"title": "Tomato farming update", "publishedAt": "2026-10-10T08:00:00Z",
                    "description": "Article summary", "url": "https://news.example/article", "image": None,
                    "source": {"name": "Example News"}}]}
        with patch.object(main, "get_secret", return_value="private-gnews-key"), \
             patch.object(main, "external_json", return_value=payload) as request:
            response = TestClient(main.app).get("/api/news?q=%20tomato%20%20care%20&lang=hi&country=in&sortBy=relevance")
        self.assertEqual(response.status_code, 200)
        item = response.json()[0]
        self.assertEqual(item["headline"], "Tomato farming update")
        self.assertEqual(item["source"], "Example News")
        self.assertEqual(item["date"], "2026-10-10T08:00:00Z")
        self.assertEqual(item["url"], "https://news.example/article")
        self.assertEqual(item["data_source"], "GNews")
        self.assertNotIn("private-gnews-key", response.text)
        upstream_params = main.urllib.parse.parse_qs(main.urllib.parse.urlparse(request.call_args.args[0]).query)
        self.assertEqual(upstream_params["q"], ["tomato care"])
        self.assertEqual(upstream_params["lang"], ["hi"])
        self.assertEqual(upstream_params["country"], ["in"])
        self.assertEqual(upstream_params["sortby"], ["relevance"])
        self.assertEqual(upstream_params["max"], ["10"])
        self.assertIn("apikey", upstream_params)
        self.assertEqual(request.call_args.kwargs["timeout"], 10)

    def test_empty_whitespace_and_overlong_query_are_rejected_without_provider_calls(self):
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json") as request:
            client = TestClient(main.app)
            self.assertEqual(client.get("/api/news?q=%20%20").status_code, 422)
            self.assertEqual(client.get("/api/news?q=" + "a" * 201).status_code, 422)
            self.assertEqual(client.get("/api/news").status_code, 422)
        request.assert_not_called()

    def test_empty_results_are_returned_as_empty_not_demo(self):
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "external_json", return_value={"articles": []}), \
             patch.object(main, "fetch_all", side_effect=AssertionError("demo rows must not be used")):
            response = TestClient(main.app).get("/api/news?q=irrigation")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_missing_optional_fields_are_not_fabricated_and_unsafe_urls_are_removed(self):
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "external_json", return_value={"articles": [{"title": "Real title", "url": "javascript:alert(1)", "image": "data:text/html,bad"}]}):
            response = TestClient(main.app).get("/api/news?q=irrigation")
        item = response.json()[0]
        self.assertEqual(item["headline"], "Real title")
        self.assertIsNone(item["source"])
        self.assertIsNone(item["date"])
        self.assertIsNone(item["summary"])
        self.assertIsNone(item["url"])
        self.assertIsNone(item["image"])
        self.assertNotIn("category", item)

    def test_missing_key_is_explicit_and_never_returns_demo_articles(self):
        with patch.object(main, "get_secret", return_value=""), \
             patch.object(main, "fetch_all", side_effect=AssertionError("demo fallback must not be used")), \
             patch.object(main, "external_json") as request:
            response = TestClient(main.app).get("/api/news?q=agriculture")
        self.assertEqual(response.status_code, 503)
        self.assertIn("GNEWS_API_KEY", response.json()["detail"])
        request.assert_not_called()

    def test_provider_http_errors_have_distinct_sanitized_messages(self):
        expected = {
            400: (422, "simpler query"),
            401: (502, "did not authorize"),
            403: (429, "quota or subscription"),
            429: (429, "rate limit"),
            500: (502, "temporarily unavailable"),
            503: (502, "temporarily unavailable"),
        }
        for provider_status, (app_status, phrase) in expected.items():
            main._gnews_last_request = 0.0
            failure = main.urllib.error.HTTPError("https://gnews.example", provider_status, "private details", {}, None)
            with patch.object(main, "get_secret", return_value="private-gnews-key"), \
                 patch.object(main, "external_json", side_effect=failure):
                response = TestClient(main.app).get(f"/api/news?q=error-{provider_status}")
            self.assertEqual(response.status_code, app_status)
            self.assertIn(phrase, response.json()["detail"])
            self.assertNotIn("private-gnews-key", response.text)
            self.assertNotIn("private details", response.text)
            failure.close()

    def test_timeout_and_malformed_payload_are_not_reported_as_empty_results(self):
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", side_effect=TimeoutError("socket timed out")):
            timeout = TestClient(main.app).get("/api/news?q=timeout")
        self.assertEqual(timeout.status_code, 504)
        self.assertIn("timed out", timeout.json()["detail"])
        main._gnews_last_request = 0.0
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", return_value={"unexpected": []}):
            malformed = TestClient(main.app).get("/api/news?q=malformed")
        self.assertEqual(malformed.status_code, 502)
        self.assertIn("unreadable response", malformed.json()["detail"])

    def test_network_and_malformed_json_failures_are_clear_and_not_cached(self):
        import json
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", side_effect=main.urllib.error.URLError("offline")):
            network = TestClient(main.app).get("/api/news?q=network")
        self.assertEqual(network.status_code, 502)
        self.assertIn("could not connect", network.json()["detail"])
        main._gnews_last_request = 0.0
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", side_effect=json.JSONDecodeError("bad", "{", 0)):
            malformed = TestClient(main.app).get("/api/news?q=bad-json")
        self.assertEqual(malformed.status_code, 502)
        self.assertIn("unreadable response", malformed.json()["detail"])
        self.assertNotIn("bad-json|en||publishedAt", main._gnews_cache)

    def test_successful_search_cache_normalizes_query_and_expires(self):
        payload = {"articles": [{"title": "Cached result", "url": "https://news.example/cached"}]}
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", return_value=payload) as request:
            client = TestClient(main.app)
            first = client.get("/api/news?q=%20agriculture%20%20India%20")
            second = client.get("/api/news?q=agriculture%20India")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json(), first.json())
        request.assert_called_once()
        cache_key = "agriculture india|en||publishedAt"
        main._gnews_cache[cache_key] = (time.monotonic() - main._gnews_cache_ttl() - 1, first.json())
        main._gnews_last_request = 0.0
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", return_value={"articles": [{"title": "Fresh result"}]}) as refresh:
            expired = TestClient(main.app).get("/api/news?q=agriculture%20India")
        self.assertEqual(expired.json()[0]["headline"], "Fresh result")
        refresh.assert_called_once()

    def test_cache_key_includes_filters_and_cache_is_bounded(self):
        payload = {"articles": [{"title": "Filtered result"}]}
        main._gnews_last_request = time.monotonic() - 2
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", return_value=payload) as request:
            first = TestClient(main.app).get("/api/news?q=agriculture&lang=en")
            main._gnews_last_request = time.monotonic() - 2
            second = TestClient(main.app).get("/api/news?q=agriculture&lang=hi")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(request.call_count, 2)
        for index in range(main._GNEWS_CACHE_MAX_ENTRIES):
            main._gnews_cache[f"old-{index}"] = (time.monotonic(), [])
        main._gnews_last_request = time.monotonic() - 2
        with patch.object(main, "get_secret", return_value="configured-test-key"), patch.object(main, "external_json", return_value={"articles": []}):
            TestClient(main.app).get("/api/news?q=cache-cap")
        self.assertLessEqual(len(main._gnews_cache), main._GNEWS_CACHE_MAX_ENTRIES)

    def test_concurrent_identical_searches_share_successful_result(self):
        from concurrent.futures import ThreadPoolExecutor
        from time import sleep
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        def response():
            return client.get("/api/news?q=concurrent").json()
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "external_json", side_effect=lambda *args, **kwargs: (sleep(0.05), {"articles": [{"title": "One upstream call"}]})[1]) as request:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: response(), range(2)))
        self.assertEqual(results[0], results[1])
        request.assert_called_once()


class StorageFinderTests(unittest.TestCase):
    def test_storage_list_marks_sample_data_and_builds_encoded_keyless_directions(self):
        rows = [
            {"id": 2, "name": "Farm Store", "location": "Devanahalli, Bengaluru Rural", "distance": 18,
             "capacity": 500, "available_capacity": 320, "storage_type": "Warehouse", "price_per_day": 16, "rating": 4.5}
        ]
        with patch.object(main, "fetch_all", return_value=rows):
            response = TestClient(main.app).get("/api/storage")
        self.assertEqual(response.status_code, 200)
        item = response.json()[0]
        self.assertEqual(item["data_source"], "DEMO DATA")
        self.assertEqual(item["capacity"], 500)
        self.assertEqual(item["available_capacity"], 320)
        parsed = main.urllib.parse.urlparse(item["directions_url"])
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.google.com")
        params = main.urllib.parse.parse_qs(parsed.query)
        self.assertEqual(params, {"api": ["1"], "destination": ["Devanahalli, Bengaluru Rural"]})

    def test_storage_list_empty_results_are_empty_not_demo_fallback(self):
        with patch.object(main, "fetch_all", return_value=[]):
            response = TestClient(main.app).get("/api/storage")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_storage_details_return_sample_label_and_directions(self):
        row = {"id": 4, "name": "Cold Store", "location": "Kengeri", "distance": 21,
               "capacity": 900, "available_capacity": 400, "storage_type": "Cold Storage", "price_per_day": 25, "rating": 4.9}
        with patch.object(main, "fetch_all", return_value=[row]):
            response = TestClient(main.app).get("/api/storage/4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data_source"], "DEMO DATA")
        self.assertEqual(main.urllib.parse.parse_qs(main.urllib.parse.urlparse(response.json()["directions_url"]).query)["destination"], ["Kengeri"])

    def test_storage_details_missing_record_returns_404(self):
        with patch.object(main, "fetch_all", return_value=[]):
            response = TestClient(main.app).get("/api/storage/999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Storage not found")

    def test_storage_api_failure_can_be_retried_successfully(self):
        client = TestClient(main.app, raise_server_exceptions=False)
        with patch.object(main, "fetch_all", side_effect=[RuntimeError("database unavailable"), []]) as fetch:
            failed = client.get("/api/storage")
            recovered = client.get("/api/storage")
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json(), [])
        self.assertEqual(fetch.call_count, 2)

    def test_storage_details_failure_can_be_retried(self):
        row = {"id": 3, "name": "Dry Store", "location": "Whitefield", "distance": 10,
               "capacity": 90, "available_capacity": 70, "storage_type": "Dry Storage", "price_per_day": 14, "rating": 4.3}
        client = TestClient(main.app, raise_server_exceptions=False)
        with patch.object(main, "fetch_all", side_effect=[RuntimeError("database unavailable"), [row]]) as fetch:
            failed = client.get("/api/storage/3")
            recovered = client.get("/api/storage/3")
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()["data_source"], "DEMO DATA")
        self.assertEqual(fetch.call_count, 2)


class WeatherFailureTests(unittest.TestCase):
    def test_open_meteo_failure_returns_explicit_demo_data(self):
        with tempfile.TemporaryDirectory(dir=os.path.dirname(__file__)) as directory:
            with patch.object(main, "DB_PATH", os.path.join(directory, "weather.db")):
                main.init_db()
                with patch.object(main, "external_json", side_effect=TimeoutError("offline")):
                    weather = asyncio.run(main.get_weather())
        self.assertTrue(weather)
        self.assertEqual(weather[0]["data_status"], "DEMO")
        self.assertIn("DEMO DATA", weather[0]["data_source"])
        self.assertIsNone(weather[0]["current_temperature"])


class GeminiIntegrationTests(unittest.TestCase):
    def test_cors_allows_vite_fallback_port_only_on_loopback(self):
        client = TestClient(main.app)
        fallback = client.get("/api/assistant/status", headers={"Origin": "http://localhost:5174"})
        self.assertEqual(fallback.headers.get("access-control-allow-origin"), "http://localhost:5174")
        untrusted = client.get("/api/assistant/status", headers={"Origin": "https://example.invalid"})
        self.assertIsNone(untrusted.headers.get("access-control-allow-origin"))

    def test_gemini_retries_rate_limit_only_with_short_retry_after(self):
        headers = Message()
        headers["Retry-After"] = "1"
        rate_limited = main.urllib.error.HTTPError("https://example.invalid", 429, "rate limited", headers, None)
        with patch.object(main, "external_json", side_effect=[rate_limited, {"ok": True}]) as request, \
             patch.object(main.time, "sleep") as sleep:
            result = main.request_gemini_json("https://example.invalid", {}, b"{}")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_gemini_does_not_retry_rate_limit_without_retry_after(self):
        rate_limited = main.urllib.error.HTTPError("https://example.invalid", 429, "quota exhausted", {}, None)
        with patch.object(main, "external_json", side_effect=rate_limited) as request, \
             patch.object(main.time, "sleep") as sleep:
            with self.assertRaises(main.urllib.error.HTTPError):
                main.request_gemini_json("https://example.invalid", {}, b"{}")
        request.assert_called_once()
        sleep.assert_not_called()
        rate_limited.close()

    def test_gemini_does_not_retry_invalid_key(self):
        invalid_key = main.urllib.error.HTTPError("https://example.invalid", 403, "forbidden", {}, None)
        with patch.object(main, "external_json", side_effect=invalid_key) as request:
            with self.assertRaises(main.urllib.error.HTTPError):
                main.request_gemini_json("https://example.invalid", {}, b"{}")
        request.assert_called_once()
        self.assertIn("rejected the API key", main.safe_external_error(invalid_key))
        invalid_key.close()

    def test_gemini_retries_timeout_and_temporary_server_error(self):
        with patch.object(main, "external_json", side_effect=[TimeoutError("slow"), {"ok": True}]) as request, \
             patch.object(main.time, "sleep") as sleep:
            result = main.request_gemini_json("https://example.invalid", {}, b"{}")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args.kwargs["timeout"], 15)
        sleep.assert_called_once_with(0.5)

        unavailable = main.urllib.error.HTTPError("https://example.invalid", 503, "unavailable", {}, None)
        with patch.object(main, "external_json", side_effect=[unavailable, {"ok": True}]) as request, \
             patch.object(main.time, "sleep") as sleep:
            result = main.request_gemini_json("https://example.invalid", {}, b"{}")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(0.5)

    def test_gemini_retry_count_is_bounded_for_repeated_429(self):
        rate_limited = main.urllib.error.HTTPError("https://example.invalid", 429, "rate limited", {}, None)
        with patch.object(main, "external_json", side_effect=rate_limited) as request, \
             patch.object(main.time, "sleep"):
            with self.assertRaises(main.urllib.error.HTTPError):
                main.request_gemini_json("https://example.invalid", {}, b"{}")
        self.assertEqual(request.call_count, 1)
        rate_limited.close()

    def test_assistant_uses_low_thinking_for_shorter_response_latency(self):
        captured = {}

        def fake_request(url, headers, body):
            captured["url"] = url
            captured["payload"] = main.json.loads(body)
            return {"candidates": [{"content": {"parts": [{"text": "General tomato guidance."}]}}]}

        decision = {"recommendation": "WAIT", "confidence": 0, "reasons": []}
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "score_to_decision", return_value=decision), \
             patch.object(main, "fetch_all", return_value=[]), \
             patch.object(main, "get_weather", return_value=[]), \
             patch.object(main, "get_market_rows", return_value=[]), \
             patch.object(main, "request_gemini_json", side_effect=fake_request):
            asyncio.run(main.ask_assistant(main.AssistantRequest(message="How should I water tomatoes?")))

        self.assertTrue(captured["url"].endswith("/v1beta/models/gemini-3.8-flash:generateContent"))
        self.assertEqual(captured["payload"]["generationConfig"]["thinkingConfig"]["thinkingLevel"], "low")
        self.assertEqual(captured["payload"]["generationConfig"]["maxOutputTokens"], 768)

    def test_assistant_keeps_deterministic_decision_in_response(self):
        decision = {"recommendation": "WAIT", "confidence": 0, "reasons": ["Market inputs are missing"]}
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "score_to_decision", return_value=decision), \
             patch.object(main, "fetch_all", return_value=[]), \
             patch.object(main, "get_weather", return_value=[]), \
             patch.object(main, "get_market_rows", return_value=[]), \
             patch.object(main, "request_gemini_json", return_value={"candidates": [{"content": {"parts": [{"text": "General tomato guidance."}]}}]}):
            response = asyncio.run(main.ask_assistant(main.AssistantRequest(message="How should I water tomatoes?")))
        self.assertEqual(response["recommendation"], "WAIT")
        self.assertEqual(response["reasons"], ["Market inputs are missing"])
        self.assertTrue(response["answer"].startswith("General tomato guidance."))

    def test_assistant_does_not_call_gemini_when_key_is_missing(self):
        with patch.object(main, "get_secret", return_value=""), \
             patch.object(main, "score_to_decision", return_value={"recommendation": "WAIT", "confidence": 0, "reasons": []}), \
             patch.object(main, "fetch_all", return_value=[]), \
             patch.object(main, "get_weather", return_value=[]), \
             patch.object(main, "get_market_rows", return_value=[]), \
             patch.object(main, "request_gemini_json") as request:
            response = asyncio.run(main.ask_assistant(main.AssistantRequest(message="How do I water tomatoes?")))
        self.assertEqual(response["status"], "unavailable")
        self.assertIn("GEMINI_API_KEY is not configured", response["answer"])
        request.assert_not_called()

    def test_malformed_gemini_response_returns_safe_error(self):
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "score_to_decision", return_value={"recommendation": "WAIT", "confidence": 0, "reasons": []}), \
             patch.object(main, "fetch_all", return_value=[]), \
             patch.object(main, "get_weather", return_value=[]), \
             patch.object(main, "get_market_rows", return_value=[]), \
             patch.object(main, "request_gemini_json", return_value={"candidates": []}):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.ask_assistant(main.AssistantRequest(message="How do I water tomatoes?")))
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("unexpected response", raised.exception.detail)

    def test_gemini_quota_error_is_sanitized_and_preserves_http_429(self):
        quota_error = main.urllib.error.HTTPError(
            "https://example.invalid", 429, "quota exhausted", {}, None
        )
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "score_to_decision", return_value={"recommendation": "WAIT", "confidence": 0, "reasons": []}), \
             patch.object(main, "fetch_all", return_value=[]), \
             patch.object(main, "get_weather", return_value=[]), \
             patch.object(main, "get_market_rows", return_value=[]), \
             patch.object(main, "request_gemini_json", side_effect=quota_error):
            response = TestClient(main.app).post(
                "/api/assistant",
                json={"message": "How should I water tomatoes?", "crop": "Tomato", "location": "Bengaluru", "language": "en"},
            )
        self.assertEqual(response.status_code, 429)
        self.assertIn("rate limited", response.json()["detail"])
        self.assertNotIn("configured-test-key", response.text)
        quota_error.close()

    def test_http_status_and_chat_routes_do_not_return_secret(self):
        client = TestClient(main.app)
        with patch.object(main, "get_secret", return_value="configured-test-key"):
            status = client.get("/api/assistant/status")
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["configured"])
        self.assertNotIn("configured-test-key", status.text)

        decision = {"recommendation": "WAIT", "confidence": 0, "reasons": ["Missing inputs"]}
        with patch.object(main, "get_secret", return_value="configured-test-key"), \
             patch.object(main, "score_to_decision", return_value=decision), \
             patch.object(main, "fetch_all", return_value=[]), \
             patch.object(main, "get_weather", new=AsyncMock(return_value=[])), \
             patch.object(main, "get_market_rows", new=AsyncMock(return_value=[])), \
             patch.object(main, "request_gemini_json", return_value={"candidates": [{"content": {"parts": [{"text": "Water tomatoes at the soil line."}]}}]}):
            response = client.post("/api/assistant", json={"message": "How should I water tomatoes?", "crop": "Tomato", "location": "Bengaluru", "language": "en"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommendation"], "WAIT")
        self.assertIn("Water tomatoes", response.json()["answer"])
        self.assertNotIn("configured-test-key", response.text)

    def test_model_setting_is_read_from_backend_configuration(self):
        with patch.object(main, "get_secret", return_value="gemini-3.8-flash"):
            self.assertEqual(main.get_gemini_model(), "gemini-3.8-flash")


class FarmToolsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory(dir=os.path.dirname(__file__))
        self.db_path = os.path.join(self.temp_directory.name, "farm-tools.db")
        self.db_patch = patch.object(main, "DB_PATH", self.db_path)
        self.db_patch.start()
        main.init_db()
        self.client = TestClient(main.app)
        main._auth_attempts.clear()
        self.accounts = []
        for name, email in (("Farmer One", "one@example.test"), ("Farmer Two", "two@example.test")):
            result = self.client.post("/api/auth/signup", json={"name": name, "email": email, "password": "Strong-password-123!"}).json()
            self.accounts.append({"name": name, "headers": {"Authorization": f"Bearer {result['access_token']}"}})

    def tearDown(self):
        self.client.close(); self.db_patch.stop(); self.temp_directory.cleanup(); main._auth_attempts.clear()

    def test_planner_journal_and_harvest_records_are_owned_and_validated(self):
        first, second = self.accounts
        crop = self.client.post("/api/farm-tools/planner-crops", headers=first["headers"], json={"data": {"crop": "Tomato", "planting_date": "2026-01-01", "area": 1.5, "stage": "Flowering", "harvest_date": "2026-04-01"}})
        self.assertEqual(crop.status_code, 201)
        task = self.client.post("/api/farm-tools/planner-tasks", headers=first["headers"], json={"data": {"title": "Inspect plants", "crop": "Tomato", "description": "Check leaves", "date": "2026-02-01", "priority": "High", "status": "Pending"}})
        self.assertEqual(task.status_code, 201)
        changed = self.client.put(f"/api/farm-tools/planner-tasks/{task.json()['id']}", headers=first["headers"], json={"data": {"title": "Inspect plants", "crop": "Tomato", "description": "Completed check", "date": "2026-02-01", "priority": "High", "status": "Completed"}})
        self.assertEqual(changed.json()["status"], "Completed")
        self.assertEqual(self.client.get("/api/farm-tools/planner-tasks", headers=second["headers"]).json(), [])
        self.assertEqual(self.client.delete(f"/api/farm-tools/planner-tasks/{task.json()['id']}", headers=second["headers"]).status_code, 404)
        journal = self.client.post("/api/farm-tools/crop-journal", headers=first["headers"], json={"data": {"crop": "Tomato", "date": "2026-02-01", "stage": "Flowering", "symptoms": "Spots", "observations": "Three leaves", "notes": ""}})
        self.assertEqual(journal.status_code, 201)
        self.assertEqual(self.client.get("/api/farm-tools/crop-journal", headers=second["headers"]).json(), [])
        harvest = self.client.post("/api/farm-tools/harvest", headers=first["headers"], json={"data": {"crop": "Tomato", "date": "2026-02-02", "quantity": 20, "sold": 5, "stored": 10, "spoiled": 2, "unit": "kg"}})
        self.assertEqual(harvest.json()["remaining"], 3)
        invalid = self.client.post("/api/farm-tools/harvest", headers=first["headers"], json={"data": {"crop": "Tomato", "date": "2026-02-02", "quantity": 10, "sold": 8, "stored": 5, "spoiled": 0, "unit": "kg"}})
        self.assertEqual(invalid.status_code, 422)

    def test_profit_estimate_converts_units_and_report_is_account_scoped(self):
        first, second = self.accounts
        result = self.client.post("/api/farm-tools/profit", headers=first["headers"], json={"data": {"crop": "Tomato", "scenario": "Market A", "quantity": 1, "unit": "tonnes", "price": 2500, "price_unit": "quintal", "transport": 1000, "labour": 0, "packaging": 0, "storage": 0, "other": 0, "loss_percent": 10}})
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()["quantity_kg_after_loss"], 900)
        self.assertEqual(result.json()["gross_revenue"], 22500)
        self.assertEqual(result.json()["total_expenses"], 1000)
        self.assertEqual(result.json()["net"], 21500)
        report = self.client.get("/api/farm-tools/report", headers=first["headers"]).json()
        self.assertEqual(report["farmer"]["name"], first["name"])
        self.assertEqual(len(report["profit_calculations"]), 1)
        self.assertEqual(self.client.get("/api/farm-tools/report", headers=second["headers"]).json()["profit_calculations"], [])
        self.assertEqual(self.client.get("/api/farm-tools/report").status_code, 401)

    def test_farmer_records_reject_negative_profit_and_invalid_dates(self):
        headers = self.accounts[0]["headers"]
        response = self.client.post("/api/farm-tools/profit", headers=headers, json={"data": {"crop": "Tomato", "scenario": "Bad", "quantity": 2, "unit": "kg", "price": 4, "price_unit": "kg", "transport": -5}})
        self.assertEqual(response.status_code, 422)
        task = self.client.post("/api/farm-tools/planner-tasks", headers=headers, json={"data": {"title": "Task", "crop": "Tomato", "description": "Notes", "date": "not-a-date", "priority": "Medium", "status": "Pending"}})
        self.assertEqual(task.status_code, 422)
        with self.assertRaises(HTTPException):
            main._farm_tool_validate("profit", {"crop": "Tomato", "scenario": "NaN", "quantity": 2, "unit": "kg", "price": float("nan"), "price_unit": "kg"})


if __name__ == "__main__":
    unittest.main()
