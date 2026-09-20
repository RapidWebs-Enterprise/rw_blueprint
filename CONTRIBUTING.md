# CONTRIBUTING

First off, thanks for taking the time to contribute! ❤️

All types of contributions are encouraged and valued. See the [Table of Contents](#table-of-contents) for different ways to help and details about how this project handles them. Please make sure to read the relevant section before making your contribution. It will make it a lot easier for us maintainers and smooth out the experience for all involved. The community looks forward to your contributions. 🎉

> And if you like the project, but just don't have time to contribute, that's fine. There are other easy ways to support the project and show your appreciation, which we would also be very happy about:
> - Star the project
> - Refer this project in your project's readme
> - Mention the project at local meetups and tell your friends/colleagues

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [I Have a Question](#i-have-a-question)
- [I Want To Contribute](#i-want-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Your First Code Contribution](#your-first-code-contribution)
  - [Improving The Documentation](#improving-the-documentation)
- [Styleguides](#styleguides)
  - [Commit Messages](#commit-messages)
- [Join The Project Team](#join-the-project-team)

## Code of Conduct

This project and everyone participating in it is governed by the [rw_blueprint Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## I Have a Question

> If you want to ask a question, we assume that you have read the available [Documentation](README.md).

Before you ask a question, it is best to search for existing [Issues](https://github.com/RapidWebs-Enterprise/rw_blueprint/issues) that might help you. In case you have found a suitable issue and still need clarification, you can write the question as a comment.

If you are still stumped, you can:
- Open an [Issue](https://github.com/RapidWebs-Enterprise/rw_blueprint/issues/new)
- Contact the maintainers

## I Want To Contribute

> ### Legal Notice
> When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content and that the content you contribute may be provided under the project license.

### Reporting Bugs

#### How Do I Submit A Good Bug Report?

> You must never report security related issues, vulnerabilities or bugs including sensitive information to the issue tracker, or elsewhere in public. Instead sensitive bugs must be sent by email to security@rapidwebs.org.

Bugs are tracked as [GitHub issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues). Create an [issue](https://github.com/RapidWebs-Enterprise/rw_blueprint/issues/new) and provide the following information by filling in the template.

Explain the problem and include additional details to help maintainers reproduce the problem:

- **Use a clear and descriptive title** for the issue to identify the problem.
- **Describe the exact steps which reproduce the problem** in as many details as possible.
- **Provide specific examples to demonstrate the steps**.

Provide more context by answering these questions:

- Did the problem start happening recently (e.g. after updating to a new version) or was this always a problem?
- Can you reliably reproduce the issue? If not, provide details about how often the problem happens and under which conditions it usually happens.

### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion, including completely new features and minor improvements to existing functionality.

Explain the enhancement and provide details to help understand the use case:

- **Use a clear and descriptive title** for the issue to identify the suggestion.
- **Provide a step-by-step description of the suggested enhancement** in as many details as possible.
- **Provide specific examples to demonstrate the steps**.
- **Describe the current behavior and the behavior you盼望 to see**.

### Your First Code Contribution

Unsure where to begin contributing to this project? You can start by looking through these beginner and help-needed issues:

- Beginner issues - issues which should only require a few lines of code, and a test or two.
- Help needed issues - issues which should be a bit more involved than beginner issues.

#### Development Environment

1. Fork the repo
2. Clone your fork
3. Install dependencies: `uv pip install -e ".[dev]"`
4. Create a branch: `git checkout -b feature/my-feature`
5. Make changes
6. Run tests: `uv run pytest`
7. Commit with conventional commits: `feat: add new feature`
8. Push and open PR

### Improving The Documentation

Documentation improvements are always welcome! This includes:
- Fixing typos
- Adding examples
- Improving clarity
- Translations

## Styleguides

### Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

Format: `<type>(<scope>): <description>`

Types:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `test`: Adding or modifying tests
- `chore`: Changes to the build process or auxiliary tools

Example:
```
feat(deployer): add dry-run mode for deployment preview
fix(schema): validate image_config optional fields
docs: update README with new CLI commands
test: add integration tests for multi-node deployment
```

## Join The Project Team

View [open issues](https://github.com/RapidWebs-Enterprise/rw_blueprint/issues) and join the discussion.

---

Thank you for contributing to rw_blueprint! 🚀
