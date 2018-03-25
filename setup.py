from setuptools import setup
 
setup(
    name='xpyth',
    packages=['xpyth'],
    version='0.2.0',
    description='Generate XPath expressions from Python comprehensions',
    license='MIT',
    author='H. Chase Stevens',
    author_email='chase@chasestevens.com',
    url='https://github.com/hchasestevens/xpyth',
    install_requires=[
        'lxml>=4.1.1',
        'pony>=0.7.3',
    ],
    tests_require=['pytest>=3.1.2'],
    extras_require={'dev': ['pytest>=3.1.2']},
    keywords='xpath xml html',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Code Generators',
    ]
)