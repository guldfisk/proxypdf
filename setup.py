from setuptools import setup

setup(
	name='proxypdf',
	version='1.0',
	packages=['proxypdf'],

	install_requires=[
		'reportlab',
		'pillow',
	]
)