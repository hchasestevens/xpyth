from setuptools import setup
 
setup(
    name = 'xpyth',
    packages = ['xpyth'],
    version = '0.1.0',
    description = 'Generates XPath expressions from Python generators',
    license='MIT',
    author='H. Chase Stevens',
    author_email='chase@chasestevens.com',
    url='https://github.com/hchasestevens/xpyth',
    install_requires=[
        'lxml',
        'pony'
    ],
    keywords='xpath xml html',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Code Generators',
    ]
)