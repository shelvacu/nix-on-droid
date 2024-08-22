from setuptools import setup, find_packages

setup(
    name='nix-on-droid-deploy-script',
    version='0.0',
    packages=[],
    #scripts = [ "deploy.py" ],
    py_modules=["deploy"],
    #package_data={"deploy.py": ["py.typed"]},
    entry_points={
        'console_scripts': [
            'deploy=deploy:go',
        ],
    },
)
