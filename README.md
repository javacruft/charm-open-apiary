# open-apiary

## Description

Open Apiary is a web application that helps you manage your apiaries
and bee hives. It's built with ease and simplicity in mind, allowing
you to access your hive records from anywhere with an internet
connection.

## Usage

To deploy Open Apiary:

    juju deploy open-apiary
    juju deploy nginx-ingress-controller
    juju add-relation open-apiary nginx-ingress-controller

## Configuration

Open Apiary uses the OpenWeather API to get weather data and is used
to pre-populate the weather data for new inspections.

To get a token, please visit the registration page for OpenWeather.
The Free Tier is perfectly acceptable for Open Apiary - it only uses
the current weather API and caches calls for 10 minutes avoiding any
problems with rate-limiting.

You can then provide your API key using the weather-api-token
configuration option:

    juju config open-apiary weather-api-token=>mytoken<

## Developing

Create and activate a virtualenv with the development requirements:

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests
